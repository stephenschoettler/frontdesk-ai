import os
import asyncio
import logging
import argparse
import signal
import urllib.parse
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, Request, Response
from starlette.websockets import WebSocketState
import uvicorn
import datetime

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.frames.frames import TextFrame
from pipecat.serializers.twilio import TwilioFrameSerializer
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
)
from pipecat.runner.utils import parse_telephony_websocket
from services.supabase_client import get_or_create_contact, log_conversation

# Import our new tool handlers
from services.llm_tools import (
    handle_get_available_slots,
    handle_book_appointment,
    handle_save_contact_name,
)

from twilio.twiml.voice_response import VoiceResponse, Connect, Stream


# Load environment variables
load_dotenv()

CLIENT_ID = os.environ.get("CLIENT_ID")


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("frontdesk.log"),
        logging.StreamHandler(),  # Keep console output for immediate feedback
    ],
)
logger = logging.getLogger(__name__)

# --- Diagnostic ---
logger.info(f"DIAGNOSTIC: Loaded SUPABASE_URL: {os.environ.get('SUPABASE_URL')}")
key_check = os.environ.get("SUPABASE_ANON_KEY")
if key_check:
    logger.info(f"DIAGNOSTIC: Loaded SUPABASE_ANON_KEY ends with: ...{key_check[-4:]}")
else:
    logger.info("DIAGNOSTIC: SUPABASE_ANON_KEY IS NOT LOADED (None).")
# ------------------

#
# AI Services
#
with open("system_prompt.txt", "r") as f:
    system_prompt = f.read()

stt = DeepgramSTTService(
    api_key=os.environ["DEEPGRAM_API_KEY"], model="nova-2-phonecall", vad_events=True
)
tts = ElevenLabsTTSService(
    api_key=os.environ["ELEVENLABS_API_KEY"],
    voice_id="21m00Tcm4TlvDq8ikWAM",  # Rachel
    model_id="eleven_flash_v2_5",
    optimize_streaming_latency=4,  # 0-4 scale
)


# Debug: Log raw LLM responses
class DebugLLM(OpenAILLMService):
    async def run_llm(self, *args, **kwargs):
        response = await super().run_llm(*args, **kwargs)
        logger.info(
            f"RAW LLM RESPONSE: {response}"
        )  # <-- Logs full output (tools/text)
        return response


llm = DebugLLM(
    api_key=os.environ["OPENROUTER_API_KEY"],
    base_url="https://openrouter.ai/api/v1",
    model="openai/gpt-4o-2024-08-06",
    temperature=0.0,
    tool_choice="auto",  # <-- Change to "auto" (required can skip in realtime)
)

# Register our tool handlers as "direct functions"
# Pipecat will auto-generate the schema from the function's docstring and type hints.
llm.register_direct_function(handle_get_available_slots)
llm.register_direct_function(handle_book_appointment)
llm.register_direct_function(handle_save_contact_name)

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

    contact = None
    caller_phone = urllib.parse.unquote(caller_phone) if caller_phone else None
    if caller_phone:
        contact = await get_or_create_contact(caller_phone)

    contact_context_message = ""
    if contact:
        if contact.get("name"):
            contact_context_message = (
                f"Known caller: {contact['name']} (phone: {contact['phone']})"
            )
        else:
            contact_context_message = (
                f"Returning caller (name unknown) (phone: {contact['phone']})"
            )
    elif caller_phone:
        contact_context_message = f"New caller (phone: {caller_phone})"

    if contact_context_message:
        logger.info(contact_context_message)

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

    current_date = datetime.date.today()
    current_day = current_date.strftime("%A")
    date_context = f"Current date: {current_date} ({current_day}). Use this to accurately calculate dates and days of the week."

    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
        {"role": "system", "content": f"CALLER CONTEXT: {contact_context_message}"},
        {"role": "system", "content": date_context},
    ]
    logger.info(f"LLM Messages: {messages}")
    # Get tools from LLM
    from pipecat.adapters.schemas.tools_schema import ToolsSchema
    from pipecat.adapters.schemas.direct_function import DirectFunctionWrapper

    tools_list = []
    for item in llm._functions.values():
        if isinstance(item.handler, DirectFunctionWrapper):
            tools_list.append(item.handler.to_function_schema())
    tools = ToolsSchema(standard_tools=tools_list)
    context = LLMContext(messages, tools=tools)  # Pass tools explicitly as second arg
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
    await task.queue_frames(
        [
            TextFrame("Hi, I'm Front Desk — your friendly AI receptionist."),
            TextFrame("How can I help you today?"),
        ]
    )

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
            if contact and contact.get("id"):
                logger.info(f"Logging conversation for contact ID: {contact['id']}...")
                # NOTE: This is the 'id' (UUID) you copied from your 'clients' table
                await log_conversation(
                    contact_id=contact["id"],
                    client_id=CLIENT_ID,
                    transcript=context.messages,
                )
                logger.info("Conversation logged successfully.")
            else:
                logger.warning("No contact with ID found, skipping conversation log.")
        except Exception as e:
            logger.error(f"Failed to log conversation: {e}")
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
    parser.add_argument(
        "--test-mode",
        action="store_true",
        help="Run in test mode, handling one call and then exiting.",
    )
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
            logger.info(
                "Running in test mode. The server will shut down after the first call."
            )
        await shutdown_event.wait()
    finally:
        logger.info(
            "Shutdown signal received. Stopping server and runner concurrently."
        )
        # Set the server to exit
        server.should_exit = True
        # Concurrently shut down the server and cancel the runner
        shutdown_tasks = [server_task, runner.cancel()]
        await asyncio.gather(*shutdown_tasks, return_exceptions=True)
        logger.info("Server and runner stopped gracefully.")


if __name__ == "__main__":
    asyncio.run(main())
    logger.info("Application exited.")
