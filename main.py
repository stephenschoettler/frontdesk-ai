import os
import asyncio
import logging
import argparse
import signal
import urllib.parse
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, Request, Response
from starlette.websockets import WebSocketState
import uvicorn

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.frames.frames import LLMRunFrame, TextFrame
from pipecat.serializers.twilio import TwilioFrameSerializer
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.runner.utils import parse_telephony_websocket
from services.supabase_client import log_call
from twilio.twiml.voice_response import VoiceResponse, Connect, Stream


# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("frontdesk.log"),
        logging.StreamHandler() # Keep console output for immediate feedback
    ]
)
logger = logging.getLogger(__name__)

#
# AI Services
#
with open("system_prompt.txt", "r") as f:
    system_prompt = f.read()

stt = DeepgramSTTService(
    api_key=os.environ["DEEPGRAM_API_KEY"],
    model="nova-2-phonecall",
    vad_events=True
)
llm = OpenAILLMService(
    api_key=os.environ["OPENROUTER_API_KEY"],
    base_url="https://openrouter.ai/api/v1",
    model="google/gemini-2.0-flash-lite-001",
)
tts = ElevenLabsTTSService(
    api_key=os.environ["ELEVENLABS_API_KEY"],
    voice_id="21m00Tcm4TlvDq8ikWAM", # Rachel
    model_id="eleven_flash_v2_5",
    optimize_streaming_latency=4  # 0-4 scale
)

#
# FastAPI App
#
app = FastAPI()

@app.post("/voice")
async def voice_handler(request: Request):
    """Handle Twilio's initial POST request and return TwiML to connect to WebSocket."""
    host = request.headers.get("host")
    form_data = await request.form()
    from_number = form_data.get("From")
    logger.info(f"Received call from: {from_number}")

    # URL-encode the phone number to handle the '+' sign
    encoded_from_number = urllib.parse.quote(from_number) if from_number else ""

    response = VoiceResponse()
    connect = Connect()
    stream_url = f"wss://{host}/ws/{encoded_from_number}"
    logger.info(f"Streaming to: {stream_url}")
    stream = Stream(url=stream_url)
    connect.append(stream)
    response.append(connect)
    return Response(content=str(response), media_type="application/xml")

@app.websocket("/ws/{caller_phone:path}")
async def websocket_endpoint(websocket: WebSocket, caller_phone: str):
    """Main websocket endpoint for the Pipecat service."""
    runner: PipelineRunner = websocket.app.state.runner
    test_mode: bool = websocket.app.state.test_mode
    shutdown_event: asyncio.Event = websocket.app.state.shutdown_event

    logger.info("New websocket connection established.")
    await websocket.accept()

    _, call_data = await parse_telephony_websocket(websocket)

    logger.info(f"Call data: {call_data}")
    caller_phone = urllib.parse.unquote(caller_phone) if caller_phone else None
    logger.info(f"Caller phone from path: {caller_phone}")

    serializer = TwilioFrameSerializer(
        stream_sid=call_data["stream_id"],
        call_sid=call_data["call_id"],
        account_sid=os.getenv("TWILIO_ACCOUNT_SID", ""),
        auth_token=os.getenv("TWILIO_AUTH_TOKEN", ""),
    )

    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            serializer=serializer,
        ),
    )

    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
    ]
    context = LLMContext(messages)
    context_aggregator = LLMContextAggregatorPair(context)

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            context_aggregator.user(),
            llm,
            tts,
            transport.output(),
            context_aggregator.assistant(),
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            audio_in_sample_rate=8000,
            audio_out_sample_rate=8000,
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
    )

    # Send an initial greeting
    await task.queue_frames([
        TextFrame("Hi, I'm Front Desk — your friendly AI receptionist."),
        TextFrame("How can I help you today?"),
    ])

    runner_task = asyncio.create_task(runner.run(task))

    # Wait for the websocket to disconnect.
    # We can't just loop on `websocket.receive_text()` because the transport
    # is already doing that. Instead, we'll poll the connection state.
    try:
        while websocket.client_state == WebSocketState.CONNECTED:
            await asyncio.sleep(0.1)
    except asyncio.CancelledError:
        # This can happen if the server is shutting down.
        pass
    finally:
        try:
            if caller_phone:
                logger.info("Logging call to Supabase...")
                # NOTE: This is the 'id' (UUID) you copied from your 'clients' table
                hardcoded_client_id = "ec8e7bfb-edce-407e-aaab-a2564644a0c9" 
                
                await log_call(
                    client_id=hardcoded_client_id,
                    caller_phone=caller_phone,
                    transcript=context.messages # This will be stored as JSON
                )
                logger.info("Call logged successfully.")
            else:
                logger.warning("No caller phone found, skipping call log.")
        except Exception as e:
            logger.error(f"Failed to log call: {e}")
        logger.info("Websocket disconnected. Cancelling pipeline task.")
        # This will cause the runner_task to finish.
        if not runner_task.done():
            await task.cancel()
        # Wait for the runner to finish cleaning up.
        await runner_task

    if test_mode:
        logger.info("Test mode: First call finished. Shutting down.")
        shutdown_event.set()


async def main():
    """
    Main function to run the FastAPI server and the Pipecat runner.
    This approach allows for graceful shutdown of both the server and the runner.
    """
    parser = argparse.ArgumentParser(description="Front Desk AI Receptionist")
    parser.add_argument("--test-mode", action="store_true", help="Run in test mode, handling one call and then exiting.")
    args = parser.parse_args()

    runner = PipelineRunner()
    shutdown_event = asyncio.Event()

    app.state.runner = runner
    app.state.test_mode = args.test_mode
    app.state.shutdown_event = shutdown_event

    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)

    # Start the server in the background
    server_task = asyncio.create_task(server.serve())

    # Set up a signal handler for graceful shutdown
    def signal_handler(*args):
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGINT, signal_handler)
    loop.add_signal_handler(signal.SIGTERM, signal_handler)

    try:
        if args.test_mode:
            logger.info("Running in test mode. The server will shut down after the first call.")
        await shutdown_event.wait()
    finally:
        logger.info("Shutdown signal received. Stopping server and runner concurrently.")
        # Set the server to exit
        server.should_exit = True
        # Concurrently shut down the server and cancel the runner
        shutdown_tasks = [
            server_task,
            runner.cancel()
        ]
        await asyncio.gather(*shutdown_tasks, return_exceptions=True)
        logger.info("Server and runner stopped gracefully.")


if __name__ == "__main__":
    asyncio.run(main())
    logger.info("Application exited.")
