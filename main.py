import os
import asyncio
import logging
import argparse
import signal
import urllib.parse
from dotenv import load_dotenv
from fastapi import (
    FastAPI,
    WebSocket,
    Request,
    Response,
    HTTPException,
    Depends,
    Header,
)
from fastapi.staticfiles import StaticFiles
from gotrue.errors import AuthApiError
from starlette.websockets import WebSocketState
import uvicorn
import datetime
from typing import Optional

from pydantic import BaseModel
from pydantic import EmailStr

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

# Import database functions
from services.supabase_client import (
    get_supabase_client,
    get_or_create_contact,
    get_client_config,
    log_conversation,
    update_contact_name,
    get_all_clients,
    create_client_record,
    update_client,
    delete_client,
    delete_conversation,
    get_all_contacts,
    get_conversation_logs,
    get_conversation_by_id,
    get_client_by_phone,
)

# Import tool handlers
from services.llm_tools import (
    handle_get_available_slots,
    handle_book_appointment,
    handle_save_contact_name,
)

# Import Response Filter
from services.response_filter import ToolStrippingAssistantAggregator

from twilio.twiml.voice_response import VoiceResponse, Connect, Stream


# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("frontdesk.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# --- Diagnostic ---
logger.info(f"DIAGNOSTIC: Loaded SUPABASE_URL: {os.environ.get('SUPABASE_URL')}")
# ------------------

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")


# --- Auth Dependency ---
async def get_current_user_token(authorization: str = Header(...)) -> str:
    scheme, credentials = authorization.split(" ")
    if scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authentication scheme")
    return credentials


# Helper: Initialize Services for a Specific Client
# Helper: Initialize Services for a Specific Client
async def initialize_client_services(client_id: str):
    """
    Fetches config for a specific client and initializes their AI services.
    Returns (stt, tts, llm, system_prompt, initial_greeting) or None on failure.
    """
    client_config = await get_client_config(client_id)
    if not client_config:
        logger.error(f"Failed to load config for client_id: {client_id}")
        return None

    # Extract Config
    system_prompt = client_config.get("system_prompt", "You are an AI receptionist.")
    llm_model = client_config.get("llm_model", "openai/gpt-4o-mini")
    tts_voice_id = client_config.get("tts_voice_id", "21m00Tcm4TlvDq8ikWAM")
    initial_greeting = client_config.get("initial_greeting")

    # Default to all tools if column is missing/empty (Backward Compatibility)
    enabled_tools = client_config.get("enabled_tools") or [
        "get_available_slots",
        "book_appointment",
        "save_contact_name",
    ]

    # STT (Deepgram)
    stt = DeepgramSTTService(
        api_key=os.environ["DEEPGRAM_API_KEY"],
        model="nova-2-phonecall",
        vad_events=True,
    )

    # TTS (ElevenLabs - Client Specific Voice)
    tts = ElevenLabsTTSService(
        api_key=os.environ["ELEVENLABS_API_KEY"],
        voice_id=tts_voice_id,
        model_id="eleven_flash_v2_5",
        optimize_streaming_latency=4,
    )

    # LLM (OpenRouter - Client Specific Model)
    class DebugLLM(OpenAILLMService):
        async def run_llm(self, *args, **kwargs):
            response = await super().run_llm(*args, **kwargs)  # type: ignore
            # logger.info(f"RAW LLM RESPONSE: {response}")
            return response

    llm = DebugLLM(
        api_key=os.environ["OPENROUTER_API_KEY"],
        base_url="https://openrouter.ai/api/v1",
        model=llm_model,
        temperature=0.6,
        tool_choice="auto",
        stream=True,
    )

    # --- Dynamic Tool Registration ---
    # Map database strings to actual python functions
    tool_map = {
        "get_available_slots": handle_get_available_slots,
        "book_appointment": handle_book_appointment,
        "save_contact_name": handle_save_contact_name,
    }

    logger.info(f"Enabling tools for client {client_id}: {enabled_tools}")

    for tool_name in enabled_tools:
        tool_func = tool_map.get(tool_name)
        if tool_func:
            llm.register_direct_function(tool_func)
        else:
            logger.warning(f"Unknown tool requested in config: {tool_name}")

    # Inject CLIENT_ID for tools
    os.environ["CLIENT_ID"] = client_id

    return stt, tts, llm, system_prompt, initial_greeting


@app.post("/voice")
async def voice_handler(request: Request):
    """
    Handle Twilio's initial POST request.
    Dynamic Routing: Look up the client based on the 'To' number.
    """
    host = request.headers.get("host")
    form_data = await request.form()

    from_number = form_data.get("From")
    to_number = form_data.get("To")  # The Twilio number being called

    logger.info(f"Incoming call: From {from_number} -> To {to_number}")

    # 1. Find which client owns this Twilio number
    client = await get_client_by_phone(to_number)

    # Fallback: If no match, check if a default CLIENT_ID is set in .env (Legacy Mode)
    if not client and os.environ.get("CLIENT_ID"):
        logger.warning(
            f"No client found for {to_number}, falling back to legacy CLIENT_ID."
        )
        client = {"id": os.environ.get("CLIENT_ID")}

    if not client:
        logger.error(f"REJECTING CALL: No client configuration found for {to_number}")
        resp = VoiceResponse()
        resp.say("I am sorry, but this number is not configured.")
        return Response(content=str(resp), media_type="application/xml")

    client_id = client["id"]

    # 2. Build the Websocket URL with the Client ID
    encoded_from = urllib.parse.quote(from_number) if from_number else "anonymous"
    stream_url = f"wss://{host}/ws/{client_id}/{encoded_from}"

    logger.info(f"Routing to: {stream_url}")

    response = VoiceResponse()
    connect = Connect()
    stream = Stream(url=stream_url)
    connect.append(stream)
    response.append(connect)
    return Response(content=str(response), media_type="application/xml")


@app.websocket("/ws/{client_id}/{caller_phone}")
async def websocket_endpoint(websocket: WebSocket, client_id: str, caller_phone: str):
    """
    Main websocket endpoint.
    Initializes services JUST-IN-TIME for the specific client.
    """
    # Initialize specific services for this client
    services = await initialize_client_services(client_id)
    if not services:
        logger.error(f"Failed to initialize services for client {client_id}. Closing.")
        await websocket.close()
        return

    stt, tts, llm, system_prompt, initial_greeting = services

    # Fetch Runner from app state (Runner is still global/shared resource)
    runner: PipelineRunner = websocket.app.state.runner
    test_mode: bool = websocket.app.state.test_mode
    shutdown_event: asyncio.Event = websocket.app.state.shutdown_event

    logger.info(f"Websocket connected for Client: {client_id}, Caller: {caller_phone}")
    await websocket.accept()

    # Track call start time for duration calculation
    call_start_time = datetime.datetime.now()

    _, call_data = await parse_telephony_websocket(websocket)

    # --- Contact Management (Scoped to Client) ---
    caller_phone_decoded = urllib.parse.unquote(caller_phone)
    contact = None

    # NOTE: get_or_create_contact needs to be multi-tenant aware in the future.
    # For now, we assume the phone number is the primary key, but we should eventually pass client_id.
    # We are patching this temporarily by filtering contacts by phone AND client_id in logic if needed,
    # but the DB constraint is already updated.
    if caller_phone_decoded:
        contact = await get_or_create_contact(caller_phone_decoded)
        # Note: Ideally passing client_id here to ensure we don't fetch another client's contact

    contact_context = ""
    if contact:
        name_str = contact.get("name") or "unknown"
        contact_context = f"Known caller: {name_str} (phone: {caller_phone_decoded})"
    else:
        contact_context = f"New caller (phone: {caller_phone_decoded})"

    logger.info(f"Context: {contact_context}")

    # Inject CALLER_PHONE for tools
    os.environ["CALLER_PHONE"] = caller_phone_decoded

    # --- Pipeline Setup ---
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

    # Messages & Context
    current_date = datetime.date.today().strftime("%A, %B %d, %Y")
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "system", "content": f"CALLER CONTEXT: {contact_context}"},
        {"role": "system", "content": f"Current date: {current_date}."},
    ]

    # Tool Registration
    from pipecat.adapters.schemas.tools_schema import ToolsSchema
    from pipecat.adapters.schemas.direct_function import DirectFunctionWrapper

    tools_list = []
    for item in llm._functions.values():
        if isinstance(item.handler, DirectFunctionWrapper):
            tools_list.append(item.handler.to_function_schema())
    tools = ToolsSchema(standard_tools=tools_list)

    context = LLMContext(messages, tools=tools)
    context_aggregator = LLMContextAggregatorPair(context)

    # Use our ToolStripping filter to keep code out of the TTS
    assistant_aggregator = ToolStrippingAssistantAggregator(context)

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            context_aggregator.user(),
            llm,
            tts,
            transport.output(),
            assistant_aggregator,  # Using the cleaner aggregator
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            audio_in_sample_rate=8000,
            audio_out_sample_rate=8000,
            enable_metrics=True,
        ),
    )

    # --- Initial Greeting ---
    if initial_greeting:
        # Final Robust Logic: Split by the period to deliver in two smaller, stable chunks.
        # This mitigates timing issues and premature stream closure.
        parts = initial_greeting.split(".", 1)

        if len(parts) == 2:
            # Send the introductory statement, and the question as a separate chunk
            await task.queue_frames(
                [TextFrame(parts[0].strip() + "."), TextFrame(parts[1].strip())]
            )
        else:
            # Fallback for templates without the standard question
            await task.queue_frames([TextFrame(initial_greeting)])

    runner_task = asyncio.create_task(runner.run(task))

    # --- Wait for Disconnect ---
    try:
        while websocket.client_state == WebSocketState.CONNECTED:
            await asyncio.sleep(0.1)
    except asyncio.CancelledError:
        pass
    finally:
        # Log Conversation
        if contact:
            # Calculate call duration
            call_end_time = datetime.datetime.now()
            duration_seconds = int((call_end_time - call_start_time).total_seconds())

            # Add timestamps to messages for transcript display
            transcript_with_timestamps = []
            base_time = call_end_time

            for i, message in enumerate(context.messages):
                # Skip system messages for transcript
                if isinstance(message, dict) and message.get("role") == "system":
                    continue

                # Add timestamp (approximate based on message order)
                timestamp = base_time - datetime.timedelta(seconds=len(context.messages) - i)
                if isinstance(message, dict):
                    transcript_with_timestamps.append({
                        **message,
                        "timestamp": timestamp.isoformat()
                    })
                else:
                    # Handle non-dict messages
                    transcript_with_timestamps.append({
                        "role": getattr(message, "role", "unknown"),
                        "content": getattr(message, "content", str(message)),
                        "timestamp": timestamp.isoformat()
                    })

            await log_conversation(
                contact_id=contact["id"],
                client_id=client_id,
                transcript=transcript_with_timestamps,
                duration=duration_seconds,
            )

        logger.info("Call ended. Cleaning up.")
        if not runner_task.done():
            await task.cancel()
        await runner_task

    if test_mode:
        shutdown_event.set()


# --- CRUD Endpoints ---


class ClientCreate(BaseModel):
    name: str
    cell: Optional[str] = None
    calendar_id: Optional[str] = None
    business_timezone: str = "America/Los_Angeles"
    business_start_hour: int = 9
    business_end_hour: int = 17
    llm_model: str = "openai/gpt-4o-mini"
    tts_voice_id: str = "21m00Tcm4TlvDq8ikWAM"
    initial_greeting: Optional[str] = None
    system_prompt: Optional[str] = None
    enabled_tools: Optional[list[str]] = None


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    cell: Optional[str] = None
    calendar_id: Optional[str] = None
    business_timezone: Optional[str] = None
    business_start_hour: Optional[int] = None
    business_end_hour: Optional[int] = None
    llm_model: Optional[str] = None
    tts_voice_id: Optional[str] = None
    initial_greeting: Optional[str] = None
    system_prompt: Optional[str] = None
    enabled_tools: Optional[list[str]] = None


class UserRegister(BaseModel):
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


@app.post("/api/auth/register")
async def register_user(user: UserRegister):
    supabase = get_supabase_client()
    if not supabase:
        raise HTTPException(500, "Supabase client not initialized")
    try:
        response = supabase.auth.sign_up(
            {
                "email": user.email,
                "password": user.password,
            }
        )
        if response.user:
            return {
                "message": "User registered successfully. Please check your email to verify your account.",
                "user_id": response.user.id,
                "email": response.user.email,
            }
        else:
            raise HTTPException(400, "Registration failed for an unknown reason.")
    except AuthApiError as e:
        logger.error(f"AuthApiError during registration: {e.message}")
        raise HTTPException(status_code=400, detail=e.message)
    except Exception as e:
        logger.error(f"Error during registration: {e}")
        raise HTTPException(500, "Internal server error")


@app.post("/api/auth/login")
async def login_user(user: UserLogin):
    supabase = get_supabase_client()
    if not supabase:
        raise HTTPException(500, "Supabase client not initialized")
    try:
        response = supabase.auth.sign_in_with_password(
            {
                "email": user.email,
                "password": user.password,
            }
        )
        if response.session:
            return {
                "access_token": response.session.access_token,
                "token_type": "bearer",
            }
        else:
            raise HTTPException(400, "Login failed for an unknown reason.")
    except AuthApiError as e:
        logger.error(f"AuthApiError during login: {e.message}")
        raise HTTPException(status_code=400, detail=e.message)
    except Exception as e:
        logger.error(f"Error during login: {e}")
        raise HTTPException(500, "Internal server error")


@app.get("/api/clients")
async def list_clients(token: str = Depends(get_current_user_token)):
    clients = await get_all_clients(token)
    if clients is None:
        raise HTTPException(500, "Failed to fetch clients")
    return {"clients": clients}


@app.post("/api/clients")
async def create_new_client(
    client: ClientCreate, token: str = Depends(get_current_user_token)
):
    new_client = await create_client_record(client.dict(), token)
    if new_client is None:
        raise HTTPException(500, "Failed to create client")
    return new_client


@app.get("/api/clients/{client_id}")
async def get_client(client_id: str):
    client = await get_client_config(client_id)
    if client is None:
        raise HTTPException(404, "Client not found")
    return client


@app.put("/api/clients/{client_id}")
async def update_existing_client(
    client_id: str, client: ClientUpdate, token: str = Depends(get_current_user_token)
):
    data = {k: v for k, v in client.dict().items() if v is not None}
    updated = await update_client(client_id, data, token)
    if updated is None:
        raise HTTPException(500, "Failed to update")
    return updated


@app.delete("/api/clients/{client_id}")
async def delete_existing_client(
    client_id: str, token: str = Depends(get_current_user_token)
):
    if not await delete_client(client_id, token):
        raise HTTPException(500, "Failed to delete")
    return {"message": "Deleted"}


@app.get("/api/contacts")
async def api_get_all_contacts():
    contacts = await get_all_contacts()
    if contacts is None:
        raise HTTPException(500, "Failed")
    return {"contacts": contacts}


@app.put("/api/contacts/{phone}")
async def api_update_contact_name(phone: str, request: Request):
    data = await request.json()
    name = data.get("name", "")
    if not name:
        raise HTTPException(400, "Name is required")
    success = await update_contact_name(phone, name)
    if not success:
        raise HTTPException(500, "Failed to update contact name")
    return {"message": "Contact name updated successfully"}


@app.get("/api/conversation-logs")
async def api_get_conversation_logs():
    logs = await get_conversation_logs()
    if logs is None:
        raise HTTPException(500, "Failed")
    return {"conversation_logs": logs}


@app.get("/api/conversation-logs/{conversation_id}/transcript")
async def api_get_conversation_transcript(conversation_id: str):
    conversation = await get_conversation_by_id(conversation_id)
    if not conversation:
        raise HTTPException(404, "Not found")
    return {"transcript": conversation.get("transcript")}


@app.delete("/api/conversation-logs/{conversation_id}")
async def api_delete_conversation_log(
    conversation_id: str, token: str = Depends(get_current_user_token)
):
    if not await delete_conversation(conversation_id, token):
        raise HTTPException(500, "Failed to delete")
    return {"message": "Deleted"}


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-mode", action="store_true")
    args = parser.parse_args()

    runner = PipelineRunner()
    shutdown_event = asyncio.Event()

    app.state.runner = runner
    app.state.test_mode = args.test_mode
    app.state.shutdown_event = shutdown_event

    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())

    def signal_handler(*args):
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGINT, signal_handler)
    loop.add_signal_handler(signal.SIGTERM, signal_handler)

    try:
        await shutdown_event.wait()
    finally:
        server.should_exit = True
        await asyncio.gather(server_task, runner.cancel(), return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(main())
