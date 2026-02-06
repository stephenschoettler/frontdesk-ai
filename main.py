import os
import asyncio
import logging
import argparse
import signal
import urllib.parse
from dotenv import load_dotenv
import jwt

# Load environment variables FIRST before any other imports
load_dotenv()

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
import tiktoken
import stripe

from pydantic import BaseModel
from pydantic import EmailStr

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.frames.frames import (
    TextFrame,
    InputAudioRawFrame,
    OutputAudioRawFrame,
    TTSSpeakFrame,
    StartFrame,
    TranscriptionFrame,
)
from pipecat.serializers.base_serializer import FrameSerializer
from pipecat.serializers.twilio import TwilioFrameSerializer
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
from pipecat.services.cartesia.tts import CartesiaTTSService
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
    get_client_balance,
    deduct_balance,
    adjust_client_balance,
    admin_update_client,
    get_client_ledger,
    toggle_user_status,
    log_usage_ledger,
    get_admin_ledger,
    get_admin_clients,
    get_admin_users,
    get_client_usage_stats,
    get_global_usage_stats,
    get_financial_history,
    get_cost_by_service,
    get_cost_by_client,
    get_top_expensive_calls,
)

from services.balance_manager import (
    get_service_balances,
    get_system_rates,
    update_system_rate,
)

# Import calendar auth functions
from services.calendar_auth import (
    generate_oauth_url,
    handle_oauth_callback,
    upload_service_account,
    revoke_credentials,
)

# Import user OAuth functions
from services.user_auth import (
    generate_user_oauth_url,
    handle_user_oauth_callback,
)

# Import tool handlers
from services.llm_tools import (
    handle_get_available_slots,
    handle_book_appointment,
    handle_save_contact_name,
    handle_reschedule_appointment,
    handle_cancel_appointment,
    handle_list_my_appointments,
    handle_transfer_call,
)

# Import Google Calendar functions
from services.google_calendar import get_upcoming_appointments

# Import Response Filter
from services.response_filter import ToolStrippingAssistantAggregator

# Import Template Manager
from services.template_manager import TemplateManager

# Import Price Manager
from services.price_manager import sync_openrouter_prices, get_model_price

from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Connect, Stream

# Initialize Twilio Client
twilio_client = Client(
    os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"]
)

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

# Add file handler for debugging
file_handler = logging.FileHandler('frontdesk_calls.log')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)
logging.getLogger().addHandler(file_handler)  # Also add to root logger for all modules

# --- Diagnostic ---
logger.info(f"DIAGNOSTIC: Loaded SUPABASE_URL: {os.environ.get('SUPABASE_URL')}")
# ------------------

# --- Global State ---
active_calls = {}  # call_id -> { client_id, client_name, caller_phone, start_time, owner_user_id }
transfer_requests = {}  # "client_id:caller_phone" -> { transfer_number, client_id, caller_phone, timestamp }
# --------------------


class RawAudioSerializer(FrameSerializer):
    def __init__(self):
        super().__init__()

    async def serialize(self, frame):
        if isinstance(frame, OutputAudioRawFrame):
            return frame.audio
        return None

    async def deserialize(self, data):
        if isinstance(data, bytes):
            return InputAudioRawFrame(audio=data, sample_rate=16000, num_channels=1)
        # If we get text (e.g. stringified JSON), ignore it or log it
        # The transport might occasionally send text if not configured perfectly,
        # but we only care about raw audio bytes for the STT.
        return None


app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")


# --- Auth Dependency ---
async def get_current_user_token(authorization: str = Header(...)) -> str:
    scheme, credentials = authorization.split(" ")
    if scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authentication scheme")
    return credentials


def release_twilio_number(phone_number: str) -> bool:
    """
    Releases a Twilio phone number by finding its SID and deleting it.
    """
    if not phone_number:
        return False

    try:
        # 1. Find the SID
        incoming_numbers = twilio_client.incoming_phone_numbers.list(
            phone_number=phone_number, limit=1
        )

        if incoming_numbers:
            sid = incoming_numbers[0].sid
            # 2. Delete (Release) the number
            twilio_client.incoming_phone_numbers(sid).delete()
            logger.info(f"Released Twilio number: {phone_number} (SID: {sid})")
            return True
        else:
            logger.warning(f"Twilio number not found for release: {phone_number}")
            return False

    except Exception as e:
        logger.error(f"Failed to release Twilio number {phone_number}: {e}")
        return False


async def initialize_client_services(
    client_id: str, caller_phone: Optional[str] = None
):
    """
    Fetches config and initializes AI services.
    Uses a wrapper function to inject client_id and caller_phone safely.
    """
    client_config = await get_client_config(client_id)
    if not client_config:
        logger.error(f"Failed to load config for client_id: {client_id}")
        return None

    system_prompt = client_config.get("system_prompt", "You are an AI receptionist.")
    llm_model = client_config.get("llm_model", "openai/gpt-4o-mini")
    stt_model = client_config.get("stt_model", "nova-2-phonecall")
    tts_provider = client_config.get("tts_provider", "cartesia")  # Default to Cartesia for cost savings
    tts_model = client_config.get("tts_model", "eleven_flash_v2_5")
    tts_voice_id = client_config.get("tts_voice_id", "21m00Tcm4TlvDq8ikWAM")
    initial_greeting = client_config.get("initial_greeting")

    enabled_tools = client_config.get("enabled_tools") or [
        "get_available_slots",
        "book_appointment",
        "save_contact_name",
        "reschedule_appointment",
        "cancel_appointment",
    ]

    stt = DeepgramSTTService(
        api_key=os.environ["DEEPGRAM_API_KEY"],
        model=stt_model,
        vad_events=True,
    )

    # Initialize TTS service based on provider
    if tts_provider == "cartesia":
        logger.info(f"[TTS DEBUG] Initializing Cartesia TTS - Voice: {tts_voice_id}")
        logger.info(f"[TTS DEBUG] Cartesia API Key present: {bool(os.environ.get('CARTESIA_API_KEY'))}")

        tts = CartesiaTTSService(
            api_key=os.environ["CARTESIA_API_KEY"],
            voice_id=tts_voice_id,
            model="sonic-3",  # Cartesia's default model
        )

        logger.info(f"[TTS DEBUG] Cartesia TTS service created successfully")

    else:  # elevenlabs
        logger.info(f"[TTS DEBUG] Initializing ElevenLabs TTS - Voice: {tts_voice_id}, Model: {tts_model}")
        logger.info(f"[TTS DEBUG] ElevenLabs API Key present: {bool(os.environ.get('ELEVENLABS_API_KEY'))}")

        tts = ElevenLabsTTSService(
            api_key=os.environ["ELEVENLABS_API_KEY"],
            voice_id=tts_voice_id,
            model_id=tts_model,
            optimize_streaming_latency=4,
        )

        logger.info(f"[TTS DEBUG] ElevenLabs TTS service created successfully")

    class DebugLLM(OpenAILLMService):
        async def run_llm(self, *args, **kwargs):
            return await super().run_llm(*args, **kwargs)

    llm = DebugLLM(
        api_key=os.environ["OPENROUTER_API_KEY"],
        base_url="https://openrouter.ai/api/v1",
        model=llm_model,
        temperature=0.6,
        tool_choice="auto",
        stream=True,
    )

    # --- Robust Tool Registration ---
    tool_map = {
        "get_available_slots": handle_get_available_slots,
        "book_appointment": handle_book_appointment,
        "save_contact_name": handle_save_contact_name,
        "reschedule_appointment": handle_reschedule_appointment,
        "cancel_appointment": handle_cancel_appointment,
        "list_my_appointments": handle_list_my_appointments,
        "transfer_call": handle_transfer_call,
    }

    logger.info(f"Enabling tools for client {client_id}: {enabled_tools}")

    # Helper to create a true function wrapper with metadata
    def create_tool_wrapper(func, c_id, c_phone):
        async def wrapper(params, **kwargs):
            # Inject context variables into the call
            return await func(params, client_id=c_id, caller_phone=c_phone, **kwargs)

        # Copy metadata so Pipecat can introspect it
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper

    for tool_name in enabled_tools:
        tool_func = tool_map.get(tool_name)
        if tool_func:
            # Create a SAFE wrapper with the client_id bound to it
            safe_tool = create_tool_wrapper(tool_func, client_id, caller_phone)

            # Register the wrapper
            llm.register_direct_function(safe_tool)
        else:
            logger.warning(f"Unknown tool requested in config: {tool_name}")

    # Fallback env vars (Deprecating usage, but keeping for safety)
    os.environ["CLIENT_ID"] = client_id
    if caller_phone:
        os.environ["CALLER_PHONE"] = caller_phone

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

    if client:
        # Check if client is active. Default to True for backward compatibility.
        is_active = client.get("is_active", True)
        if is_active is False:
            logger.info(f"REJECTING CALL: Client {client.get('id')} is inactive.")
            resp = VoiceResponse()
            resp.say("I am sorry, but this service is currently unavailable.")
            return Response(content=str(resp), media_type="application/xml")

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


@app.post("/transfer-callback")
async def transfer_callback_handler(request: Request):
    """
    Handle Twilio's callback after a transfer attempt.
    If the transfer fails (busy, no-answer, failed), this endpoint is called.
    We can optionally return the caller to the AI or just end the call.
    """
    form_data = await request.form()
    dial_call_status = form_data.get("DialCallStatus")
    call_sid = form_data.get("CallSid")

    logger.info(f"[TRANSFER CALLBACK] Call {call_sid} - Status: {dial_call_status}")

    response = VoiceResponse()

    # If the transfer failed, we could return to AI or take a message
    # For now, we'll just end the call politely
    if dial_call_status in ["busy", "no-answer", "failed", "canceled"]:
        logger.warning(f"[TRANSFER] Transfer failed with status: {dial_call_status}")
        response.say("I'm sorry, but the transfer could not be completed. Please try calling back later. Goodbye.")
    else:
        # Transfer succeeded - call is now connected, no need to do anything
        logger.info(f"[TRANSFER] Transfer completed successfully")

    return Response(content=str(response), media_type="application/xml")


@app.websocket("/ws/{client_id}/{caller_phone}")
async def websocket_endpoint(websocket: WebSocket, client_id: str, caller_phone: str):
    # 1. CHECK: Verify Balance
    balance_seconds = await get_client_balance(client_id)
    if balance_seconds <= 0:
        logger.warning(f"Client {client_id} has zero balance. Rejecting.")
        await websocket.close(code=4002, reason="Insufficient Funds")
        return

    caller_phone_decoded = urllib.parse.unquote(caller_phone)

    services = await initialize_client_services(client_id, caller_phone_decoded)
    if not services:
        await websocket.close()
        return
    stt, tts, llm, system_prompt, initial_greeting = services

    # Fetch Runner from app state
    runner: PipelineRunner = websocket.app.state.runner
    test_mode: bool = websocket.app.state.test_mode
    shutdown_event: asyncio.Event = websocket.app.state.shutdown_event

    logger.info(f"Websocket connected for Client: {client_id}, Caller: {caller_phone}")
    await websocket.accept()

    _, call_data = await parse_telephony_websocket(websocket)

    # --- Call Tracking (LIVE) ---
    call_id = call_data["call_id"]
    try:
        # Fetch client config again to get name and owner
        # Optimization: initialize_client_services could return this, but this is safer for now
        cc = await get_client_config(client_id)
        active_calls[call_id] = {
            "call_id": call_id,
            "client_id": client_id,
            "client_name": cc.get("name", "Unknown Agent"),
            "owner_user_id": cc.get("owner_user_id", ""),
            "caller_phone": caller_phone_decoded,
            "start_time": datetime.datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to register active call: {e}")
    # ----------------------------

    # --- Contact Management (Scoped to Client) ---
    contact = None
    if caller_phone_decoded:
        # FIX: Pass client_id to the function
        contact = await get_or_create_contact(caller_phone_decoded, client_id)

    contact_context = ""
    if contact:
        name_str = contact.get("name") or "unknown"
        contact_context = f"Known caller: {name_str} (phone: {caller_phone_decoded})"
    else:
        contact_context = f"New caller (phone: {caller_phone_decoded})"

    # --- Calendar Context Injection ---
    client_config = await get_client_config(client_id)
    if client_config:
        calendar_id = client_config.get("calendar_id", "primary")
        appt_context = await get_upcoming_appointments(
            calendar_id, caller_phone_decoded
        )
        if appt_context:
            contact_context += f"\n[EXISTING BOOKINGS]\n{appt_context}"
            logger.info(f"Injected appointments: {appt_context}")

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

    # Add initial greeting to context so LLM knows it was said
    if initial_greeting:
        messages.append({"role": "assistant", "content": initial_greeting})
        logger.info(f"[GREETING DEBUG] Added greeting to context: {initial_greeting[:50]}...")

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
    assistant_aggregator = ToolStrippingAssistantAggregator(context)

    logger.info(f"[PIPELINE DEBUG] Building pipeline with components: STT={type(stt).__name__}, LLM={type(llm).__name__}, TTS={type(tts).__name__}")

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            context_aggregator.user(),
            llm,
            tts,
            transport.output(),
            assistant_aggregator,
        ]
    )

    logger.info(f"[PIPELINE DEBUG] Pipeline created successfully")

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            audio_in_sample_rate=8000,
            audio_out_sample_rate=8000,
            enable_metrics=True,
        ),
    )

    logger.info(f"[PIPELINE DEBUG] PipelineTask created with sample rates: in=8000, out=8000")

    logger.info(f"[RUNNER DEBUG] Starting pipeline runner for call")
    runner_task = asyncio.create_task(runner.run(task))
    logger.info(f"[RUNNER DEBUG] Pipeline runner task created and running")

    # --- Trigger Initial Greeting ---
    # If initial greeting is configured, send it directly as TTS output
    if initial_greeting:
        async def trigger_greeting():
            logger.info(f"[GREETING DEBUG] Waiting for transport to be ready...")
            await asyncio.sleep(1.0)  # Wait for transport to be ready
            logger.info(f"[GREETING DEBUG] Sending greeting as TTS: {initial_greeting[:50]}...")
            # Send greeting directly to TTS
            await task.queue_frames([TTSSpeakFrame(initial_greeting)])
            logger.info(f"[GREETING DEBUG] Greeting sent to TTS")

        asyncio.create_task(trigger_greeting())

    # 2. MONITOR: Safety Valve & Cutoff
    call_start_time = datetime.datetime.now()
    last_deduction_time = call_start_time
    accumulated_deduction = 0

    async def safety_valve_sync():
        nonlocal last_deduction_time, accumulated_deduction
        try:
            while True:
                await asyncio.sleep(300)  # 5 Minutes
                now = datetime.datetime.now()
                chunk = int((now - last_deduction_time).total_seconds())
                if chunk > 0:
                    await deduct_balance(client_id, chunk)
                    last_deduction_time = now
                    accumulated_deduction += chunk
        except asyncio.CancelledError:
            pass

    safety_task = asyncio.create_task(safety_valve_sync())

    try:
        while websocket.client_state == WebSocketState.CONNECTED:
            # 3. CHECK: Transfer Request
            call_key = f"{client_id}:{caller_phone_decoded}"
            if call_key in transfer_requests:
                transfer_info = transfer_requests.pop(call_key)
                transfer_number = transfer_info["transfer_number"]

                logger.info(f"[TRANSFER] Initiating transfer for {call_key} to {transfer_number}")

                # Close the websocket stream
                await websocket.close(code=1000, reason="Transferring Call")

                # Use Twilio REST API to update the call with transfer TwiML
                try:
                    from twilio.twiml.voice_response import VoiceResponse, Dial

                    # Create TwiML for the transfer
                    response = VoiceResponse()
                    response.say("Please hold while I transfer you.")
                    dial = Dial(
                        caller_id=os.environ.get("TWILIO_PHONE_NUMBER", caller_phone_decoded),
                        timeout=30,
                        action=f"https://{websocket.headers.get('host')}/transfer-callback"
                    )
                    dial.number(transfer_number)
                    response.append(dial)

                    # Update the active call with new TwiML
                    twilio_client.calls(call_id).update(
                        twiml=str(response)
                    )

                    logger.info(f"[TRANSFER] Call {call_id} successfully transferred to {transfer_number}")
                except Exception as transfer_error:
                    logger.error(f"[TRANSFER] Failed to transfer call {call_id}: {transfer_error}")

                break

            # 4. ENFORCE: Hard Cutoff
            elapsed = (datetime.datetime.now() - call_start_time).total_seconds()
            if elapsed > balance_seconds:
                logger.warning(f"CUTOFF: Client {client_id} out of funds.")
                await websocket.close(code=4002, reason="Time Limit Exceeded")
                break
            await asyncio.sleep(0.1)
    except asyncio.CancelledError:
        logger.info(f"[CALL DEBUG] Call cancelled for {call_id}")
        pass
    finally:
        logger.info(f"[CALL DEBUG] Call ending - Duration: {(datetime.datetime.now() - call_start_time).total_seconds():.2f}s")

        # --- Cleanup Active Call ---
        active_calls.pop(call_id, None)
        # ---------------------------

        safety_task.cancel()

        # 4. COMMIT: Finalize Billing
        call_end_time = datetime.datetime.now()
        total_seconds = int((call_end_time - call_start_time).total_seconds())

        logger.info(f"[BILLING DEBUG] Total call duration: {total_seconds}s")

        remainder = total_seconds - accumulated_deduction
        if remainder > 0:
            await deduct_balance(client_id, remainder)

        # 5. METRICS: Count Tokens (The Meter)
        input_tokens = 0
        output_tokens = 0
        tts_chars = 0
        try:
            enc = tiktoken.get_encoding("o200k_base")  # GPT-4o standard
            for msg in context.messages:
                # Handle both dict and object messages (Pipecat compatibility)
                if isinstance(msg, dict):
                    role = msg.get("role", "")
                    content = str(msg.get("content", ""))
                else:
                    role = getattr(msg, "role", "")
                    content = str(getattr(msg, "content", ""))

                if role == "assistant":
                    output_tokens += len(enc.encode(content))
                    tts_chars += len(content)
                elif role in ["user", "system"]:
                    input_tokens += len(enc.encode(content))
        except Exception as e:
            logger.error(f"Token count failed: {e}")

        logger.info(f"[METRICS DEBUG] Input tokens: {input_tokens}, Output tokens: {output_tokens}, TTS chars: {tts_chars}")

        # Log Conversation & Get ID
        # Calculate transcript with timestamps
        transcript_with_timestamps = []
        base_time = call_end_time

        # Initial Greeting Timestamp
        if initial_greeting:
            greeting_timestamp = base_time - datetime.timedelta(
                seconds=len(context.messages) + 1
            )
            transcript_with_timestamps.insert(
                0,
                {
                    "role": "assistant",
                    "content": initial_greeting,
                    "timestamp": greeting_timestamp.isoformat(),
                },
            )

        for i, message in enumerate(context.messages):
            # Skip system messages for transcript
            msg_tool_calls = None  # 1. Initialize variable

            if isinstance(message, dict):
                if message.get("role") == "system":
                    continue
                msg_role = message.get("role")
                msg_content = message.get("content")
                msg_tool_calls = message.get("tool_calls")  # 2. Extract from dict
            else:
                if getattr(message, "role", "") == "system":
                    continue
                msg_role = getattr(message, "role", "")
                msg_content = getattr(message, "content", "")
                msg_tool_calls = getattr(
                    message, "tool_calls", None
                )  # 3. Extract from object

            timestamp = base_time - datetime.timedelta(
                seconds=len(context.messages) - i
            )

            # 4. Construct entry with optional tool_calls
            entry = {
                "role": msg_role,
                "content": str(msg_content),
                "timestamp": timestamp.isoformat(),
                "created_at": timestamp.isoformat(),
            }

            # 5. Attach tool_calls if they exist (This triggers the ⚡ icon in UI)
            if msg_tool_calls:
                entry["tool_calls"] = msg_tool_calls

            transcript_with_timestamps.append(entry)

        # 1. Log Conversation
        response_obj = await log_conversation(
            contact_id=contact["id"] if contact else None,
            client_id=client_id,
            transcript=transcript_with_timestamps,
            duration=total_seconds,
        )

        # 2. SAFE EXTRACTION: Get the string ID from the object
        actual_conv_id = None
        try:
            # Check if we got a valid response object with data
            if response_obj and hasattr(response_obj, "data") and response_obj.data:
                actual_conv_id = response_obj.data[0]["id"]
                logger.info(f"CAPTURED CONVERSATION ID: {actual_conv_id}")
            else:
                logger.error(
                    f"LOGGING ERROR: Could not extract ID from: {response_obj}"
                )
        except Exception as e:
            logger.error(f"LOGGING EXCEPTION: {e}")

        # 3. Log to Ledger (Only if we have a valid string ID)
        if actual_conv_id:
            # Get LLM model for pricing
            client_config = await get_client_config(client_id)
            llm_model = (
                client_config.get("llm_model", "openai/gpt-4o-mini")
                if client_config
                else "openai/gpt-4o-mini"
            )

            # Fetch dynamic system rates
            system_rates = await get_system_rates()
            # Defaults if DB fetch fails
            cost_twilio = system_rates.get("twilio_cost_per_min", 0.013)
            cost_stt = system_rates.get("stt_cost_per_min", 0.0043)
            cost_tts = system_rates.get("tts_cost_per_char", 0.00003)

            # Calculate costs
            model_price = await get_model_price(llm_model)
            if model_price:
                input_cost = input_tokens * model_price["input"]
                output_cost = output_tokens * model_price["output"]
            else:
                input_cost = 0.0
                output_cost = 0.0

            audio_minutes = total_seconds / 60
            stt_cost = audio_minutes * cost_stt
            twilio_cost = audio_minutes * cost_twilio
            combined_audio_cost = stt_cost + twilio_cost
            tts_cost = tts_chars * cost_tts

            costs = {
                "duration": combined_audio_cost,
                "llm_tokens_input": input_cost,
                "llm_tokens_output": output_cost,
                "tts_characters": tts_cost,
            }

            await log_usage_ledger(
                client_id,
                actual_conv_id,
                {
                    "duration": total_seconds,
                    "llm_tokens_input": input_tokens,
                    "llm_tokens_output": output_tokens,
                    "tts_characters": tts_chars,
                },
                costs,
            )

        logger.info("Call ended. Cleaning up.")
        if not runner_task.done():
            await task.cancel()
        await runner_task

    if test_mode:
        shutdown_event.set()


@app.websocket("/ws-simulator/{client_id}")
async def simulator_endpoint(websocket: WebSocket, client_id: str):
    # 1. CHECK: Verify Balance
    balance_seconds = await get_client_balance(client_id)
    if balance_seconds <= 0:
        logger.warning(f"Client {client_id} has zero balance. Rejecting Simulator.")
        await websocket.close(code=4002, reason="Insufficient Funds")
        return

    # Initialize with special "SIMULATOR" caller
    services = await initialize_client_services(client_id, "SIMULATOR")
    if not services:
        await websocket.close()
        return
    stt, tts, llm, system_prompt, initial_greeting = services

    # Fetch Runner from app state
    runner: PipelineRunner = websocket.app.state.runner

    logger.info(f"Simulator connected for Client: {client_id}")
    await websocket.accept()

    # --- Active Call Tracking (Simulator) ---
    call_id = f"sim-{client_id}-{int(datetime.datetime.now().timestamp())}"
    try:
        cc = await get_client_config(client_id)
        active_calls[call_id] = {
            "call_id": call_id,
            "client_id": client_id,
            "client_name": cc.get("name", "Unknown Agent"),
            "owner_user_id": cc.get("owner_user_id", ""),
            "caller_phone": "SIMULATOR",
            "start_time": datetime.datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to register simulator active call: {e}")

    # --- Pipeline Setup (Raw Audio for Browser) ---
    serializer = RawAudioSerializer()
    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            audio_in_sample_rate=16000,
            audio_out_sample_rate=16000,
            serializer=serializer,
        ),
    )

    current_date = datetime.date.today().strftime("%A, %B %d, %Y")
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "system",
            "content": "CONTEXT: User is testing via Browser Simulator.",
        },
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
    assistant_aggregator = ToolStrippingAssistantAggregator(context)

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            context_aggregator.user(),
            llm,
            tts,
            transport.output(),
            assistant_aggregator,
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            audio_in_sample_rate=16000,
            audio_out_sample_rate=16000,
            enable_metrics=True,
        ),
    )

    if initial_greeting:
        await task.queue_frames([TextFrame(initial_greeting)])

    runner_task = asyncio.create_task(runner.run(task))

    # 2. MONITOR: Safety Valve (Copied from standard endpoint)
    call_start_time = datetime.datetime.now()
    last_deduction_time = call_start_time
    accumulated_deduction = 0

    async def safety_valve_sync():
        nonlocal last_deduction_time, accumulated_deduction
        try:
            while True:
                await asyncio.sleep(300)  # 5 Minutes
                now = datetime.datetime.now()
                chunk = int((now - last_deduction_time).total_seconds())
                if chunk > 0:
                    await deduct_balance(client_id, chunk)
                    last_deduction_time = now
                    accumulated_deduction += chunk
        except asyncio.CancelledError:
            pass

    safety_task = asyncio.create_task(safety_valve_sync())

    try:
        while websocket.client_state == WebSocketState.CONNECTED:
            elapsed = (datetime.datetime.now() - call_start_time).total_seconds()
            if elapsed > balance_seconds:
                await websocket.close(code=4002, reason="Time Limit Exceeded")
                break
            await asyncio.sleep(0.1)
    except asyncio.CancelledError:
        pass
    finally:
        # --- Cleanup Active Call ---
        # Do this FIRST so UI updates immediately
        active_calls.pop(call_id, None)

        safety_task.cancel()

        # Final Billing
        call_end_time = datetime.datetime.now()
        total_seconds = int((call_end_time - call_start_time).total_seconds())
        remainder = total_seconds - accumulated_deduction
        if remainder > 0:
            await deduct_balance(client_id, remainder)

        # 5. METRICS: Count Tokens (The Meter)
        input_tokens = 0
        output_tokens = 0
        tts_chars = 0
        try:
            enc = tiktoken.get_encoding("o200k_base")  # GPT-4o standard
            for msg in context.messages:
                # Handle both dict and object messages (Pipecat compatibility)
                if isinstance(msg, dict):
                    role = msg.get("role", "")
                    content = str(msg.get("content", ""))
                else:
                    role = getattr(msg, "role", "")
                    content = str(getattr(msg, "content", ""))

                if role == "assistant":
                    output_tokens += len(enc.encode(content))
                    tts_chars += len(content)
                elif role in ["user", "system"]:
                    input_tokens += len(enc.encode(content))
        except Exception as e:
            logger.error(f"Token count failed: {e}")

        logger.info(f"[METRICS DEBUG] Input tokens: {input_tokens}, Output tokens: {output_tokens}, TTS chars: {tts_chars}")

        # Log Conversation & Get ID
        # Calculate transcript with timestamps
        transcript_with_timestamps = []
        base_time = call_end_time

        # Initial Greeting Timestamp
        if initial_greeting:
            greeting_timestamp = base_time - datetime.timedelta(
                seconds=len(context.messages) + 1
            )
            transcript_with_timestamps.insert(
                0,
                {
                    "role": "assistant",
                    "content": initial_greeting,
                    "timestamp": greeting_timestamp.isoformat(),
                },
            )

        for i, message in enumerate(context.messages):
            # Skip system messages for transcript
            msg_tool_calls = None  # 1. Initialize variable

            if isinstance(message, dict):
                if message.get("role") == "system":
                    continue
                msg_role = message.get("role")
                msg_content = message.get("content")
                msg_tool_calls = message.get("tool_calls")  # 2. Extract from dict
            else:
                if getattr(message, "role", "") == "system":
                    continue
                msg_role = getattr(message, "role", "")
                msg_content = getattr(message, "content", "")
                msg_tool_calls = getattr(
                    message, "tool_calls", None
                )  # 3. Extract from object

            timestamp = base_time - datetime.timedelta(
                seconds=len(context.messages) - i
            )

            # 4. Construct entry with optional tool_calls
            entry = {
                "role": msg_role,
                "content": str(msg_content),
                "timestamp": timestamp.isoformat(),
                "created_at": timestamp.isoformat(),
            }

            # 5. Attach tool_calls if they exist (This triggers the ⚡ icon in UI)
            if msg_tool_calls:
                entry["tool_calls"] = msg_tool_calls

            transcript_with_timestamps.append(entry)

        # 1. Log Conversation
        response_obj = await log_conversation(
            contact_id=None,
            client_id=client_id,
            transcript=transcript_with_timestamps,
            duration=total_seconds,
        )

        # 2. SAFE EXTRACTION: Get the string ID from the object
        actual_conv_id = None
        try:
            # Check if we got a valid response object with data
            if response_obj and hasattr(response_obj, "data") and response_obj.data:
                actual_conv_id = response_obj.data[0]["id"]
                logger.info(f"CAPTURED CONVERSATION ID: {actual_conv_id}")
            else:
                logger.error(
                    f"LOGGING ERROR: Could not extract ID from: {response_obj}"
                )
        except Exception as e:
            logger.error(f"LOGGING EXCEPTION: {e}")

        # 3. Log to Ledger (Only if we have a valid string ID)
        if actual_conv_id:
            # Get LLM model for pricing
            client_config = await get_client_config(client_id)
            llm_model = (
                client_config.get("llm_model", "openai/gpt-4o-mini")
                if client_config
                else "openai/gpt-4o-mini"
            )

            # Fetch dynamic system rates
            system_rates = await get_system_rates()
            # Defaults if DB fetch fails
            cost_twilio = system_rates.get("twilio_cost_per_min", 0.013)
            cost_stt = system_rates.get("stt_cost_per_min", 0.0043)
            cost_tts = system_rates.get("tts_cost_per_char", 0.00003)

            # Calculate costs
            model_price = await get_model_price(llm_model)
            if model_price:
                input_cost = input_tokens * model_price["input"]
                output_cost = output_tokens * model_price["output"]
            else:
                input_cost = 0.0
                output_cost = 0.0

            audio_minutes = total_seconds / 60
            stt_cost = audio_minutes * cost_stt
            twilio_cost = audio_minutes * cost_twilio
            combined_audio_cost = stt_cost + twilio_cost
            tts_cost = tts_chars * cost_tts

            costs = {
                "duration": combined_audio_cost,
                "llm_tokens_input": input_cost,
                "llm_tokens_output": output_cost,
                "tts_characters": tts_cost,
            }

            await log_usage_ledger(
                client_id,
                actual_conv_id,
                {
                    "duration": total_seconds,
                    "llm_tokens_input": input_tokens,
                    "llm_tokens_output": output_tokens,
                    "tts_characters": tts_chars,
                },
                costs,
            )

        if not runner_task.done():
            await task.cancel()
        try:
            await runner_task
        except Exception as e:
            logger.error(f"Simulator Runner Error (Ignored): {e}")


# --- CRUD Endpoints ---


class ClientCreate(BaseModel):
    name: str
    cell: Optional[str] = None
    selected_number: Optional[str] = None  # New field for provisioning
    calendar_id: Optional[str] = None
    is_active: bool = True
    business_timezone: str = "America/Los_Angeles"
    business_start_hour: int = 9
    business_end_hour: int = 17
    llm_model: str = "openai/gpt-4o-mini"
    stt_model: str = "nova-2-phonecall"
    tts_model: str = "eleven_flash_v2_5"
    tts_voice_id: str = "21m00Tcm4TlvDq8ikWAM"
    initial_greeting: Optional[str] = None
    system_prompt: Optional[str] = None
    enabled_tools: Optional[list[str]] = None


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    cell: Optional[str] = None
    selected_number: Optional[str] = None  # New field for late provisioning
    calendar_id: Optional[str] = None
    is_active: Optional[bool] = None
    business_timezone: Optional[str] = None
    business_start_hour: Optional[int] = None
    business_end_hour: Optional[int] = None
    llm_model: Optional[str] = None
    stt_model: Optional[str] = None
    tts_model: Optional[str] = None
    tts_voice_id: Optional[str] = None
    initial_greeting: Optional[str] = None
    system_prompt: Optional[str] = None
    enabled_tools: Optional[list[str]] = None


class CheckoutSessionRequest(BaseModel):
    client_id: str
    package_id: str


class UserRegister(BaseModel):
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class AdjustBalanceRequest(BaseModel):
    client_id: str
    amount_seconds: int
    reason: str


class AdminClientUpdate(BaseModel):
    name: Optional[str] = None
    cell: Optional[str] = None
    system_prompt: Optional[str] = None
    is_active: Optional[bool] = None
    llm_model: Optional[str] = None
    stt_model: Optional[str] = None
    tts_model: Optional[str] = None
    tts_voice_id: Optional[str] = None
    enabled_tools: Optional[list[str]] = None


class UpdateSystemRateRequest(BaseModel):
    key: str
    value: str


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


# === Google OAuth User Authentication Endpoints ===

@app.post("/api/auth/google/initiate")
async def initiate_google_login():
    """Initiate Google OAuth flow for user login."""
    try:
        logger.info("=== GOOGLE USER LOGIN INITIATE ===")
        authorization_url, state = generate_user_oauth_url()

        return {
            "authorization_url": authorization_url,
            "state": state
        }

    except ValueError as e:
        logger.error(f"ValueError in Google login initiate: {e}")
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Error initiating Google login: {e}", exc_info=True)
        raise HTTPException(500, "Failed to initiate Google login")


@app.get("/api/auth/google/callback")
async def google_login_callback(code: str, state: str):
    """Handle Google OAuth callback for user login."""
    try:
        logger.info("=== GOOGLE USER LOGIN CALLBACK ===")
        supabase = get_supabase_client()
        if not supabase:
            return Response(
                content="<html><body><h1>Error</h1><p>Database unavailable</p></body></html>",
                media_type="text/html"
            )

        # Handle OAuth callback
        result = await handle_user_oauth_callback(code, state, supabase)

        # Return HTML that closes popup and sends data to parent window
        html_content = f"""
        <html>
        <head>
            <title>Login Successful</title>
            <style>
                body {{
                    font-family: system-ui, -apple-system, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                }}
                .container {{
                    background: white;
                    padding: 2rem;
                    border-radius: 8px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                    text-align: center;
                }}
                .success {{
                    color: #10b981;
                    font-size: 3rem;
                    margin-bottom: 1rem;
                }}
                h1 {{
                    color: #1f2937;
                    margin: 0 0 0.5rem 0;
                }}
                p {{
                    color: #6b7280;
                    margin: 0;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success">✓</div>
                <h1>Login Successful</h1>
                <p>Redirecting to dashboard...</p>
            </div>
            <script>
                // Send user data to parent window
                if (window.opener) {{
                    window.opener.postMessage({{
                        type: 'google_login_success',
                        user: {result['user']},
                        token: '{result['token']}'
                    }}, '*');
                    setTimeout(() => window.close(), 1500);
                }}
            </script>
        </body>
        </html>
        """

        return Response(content=html_content, media_type="text/html")

    except ValueError as e:
        logger.error(f"ValueError in Google login callback: {e}")
        error_html = f"""
        <html>
        <head><title>Login Error</title></head>
        <body>
            <h1>Login Error</h1>
            <p>{str(e)}</p>
            <p>Please close this window and try again.</p>
        </body>
        </html>
        """
        return Response(content=error_html, media_type="text/html", status_code=400)
    except Exception as e:
        logger.error(f"Error in Google login callback: {e}", exc_info=True)
        error_html = """
        <html>
        <head><title>Login Error</title></head>
        <body>
            <h1>Login Error</h1>
            <p>An unexpected error occurred. Please try again.</p>
            <p>You can close this window.</p>
        </body>
        </html>
        """
        return Response(content=error_html, media_type="text/html", status_code=500)


@app.get("/api/twilio/available-numbers")
async def get_available_numbers(
    area_code: str, token: str = Depends(get_current_user_token)
):
    try:
        numbers = twilio_client.available_phone_numbers("US").local.list(
            area_code=area_code, limit=5
        )
        return {"numbers": [n.phone_number for n in numbers]}
    except Exception as e:
        logger.error(f"Twilio search error: {e}")
        # Return empty list or 500? Returning empty list is safer for UI, but 500 indicates failure.
        # Using 400 for bad request if area code is invalid, else 500.
        # Simple approach:
        raise HTTPException(
            status_code=400, detail=f"Failed to search numbers: {str(e)}"
        )


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
    # Refactored: "Pay First, Provision Later"
    # We no longer buy the number here. We just create the skeleton record.

    # 2. Create DB Record
    new_client = await create_client_record(
        client.dict(exclude={"selected_number"}), token
    )
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
    # 0. Check for Admin Lock
    current_config = await get_client_config(client_id)
    if current_config:
        enabled_tools = current_config.get("enabled_tools") or []
        if "ADMIN_LOCKED" in enabled_tools:
            # If trying to enable (is_active=True), block it.
            # If client.is_active is None, they aren't changing it, so it's fine.
            if client.is_active is True:
                raise HTTPException(
                    status_code=403,
                    detail="This agent has been locked by the administrator. Please contact support."
                )

    # 1. Handle Late Provisioning (if selected_number is provided)
    if client.selected_number:
        try:
            # A. Get current client to check for existing number
            current_config = await get_client_config(client_id)
            if current_config and current_config.get("cell"):
                # Release the old number!
                logger.info(
                    f"Releasing old number {current_config['cell']} for client {client_id}"
                )
                release_twilio_number(current_config["cell"])

            # B. Buy New Number
            base_url = os.environ.get("BASE_URL")
            if not base_url:
                logger.warning("BASE_URL not set. Twilio Voice URL might be incorrect.")
                base_url = "https://example.com"

            webhook_url = f"{base_url}/voice"

            purchased_number = twilio_client.incoming_phone_numbers.create(
                phone_number=client.selected_number, voice_url=webhook_url
            )

            # C. Update the 'cell' field in the update payload
            client.cell = purchased_number.phone_number
            logger.info(
                f"Provisioned Twilio Number: {client.cell} for client {client_id}"
            )

        except Exception as e:
            logger.error(f"Twilio Provisioning Failed during UPDATE: {e}")
            raise HTTPException(
                status_code=400, detail=f"Failed to purchase number: {str(e)}"
            )

    data = {
        k: v
        for k, v in client.dict().items()
        if v is not None and k != "selected_number"
    }
    updated = await update_client(client_id, data, token)
    if updated is None:
        raise HTTPException(500, "Failed to update")
    return updated


@app.delete("/api/clients/{client_id}")
async def delete_existing_client(
    client_id: str, token: str = Depends(get_current_user_token)
):
    # 1. Fetch client data to get the phone number
    client_data = await get_client_config(client_id)

    # 2. Release Twilio Number if it exists
    if client_data and client_data.get("cell"):
        release_twilio_number(client_data["cell"])

    # 3. Proceed with database deletion
    if not await delete_client(client_id, token):
        raise HTTPException(500, "Failed to delete")
    return {"message": "Deleted"}


# === Calendar Credentials Endpoints ===

@app.get("/api/clients/{client_id}/calendar/status")
async def get_calendar_auth_status(
    client_id: str, token: str = Depends(get_current_user_token)
):
    """Get calendar authentication status for a client."""
    try:
        supabase = get_supabase_client()
        if not supabase:
            raise HTTPException(500, "Database unavailable")

        # Verify user owns this client
        user_id = jwt.decode(token, options={"verify_signature": False})["sub"]
        client_data = await get_client_config(client_id)
        if not client_data or client_data.get("owner_user_id") != user_id:
            raise HTTPException(403, "Unauthorized")

        # Check for active credentials
        result = supabase.table("calendar_credentials").select(
            "credential_type, created_at, last_used_at, service_account_email"
        ).eq("client_id", client_id).eq("is_active", True).execute()

        # Check if global fallback is available
        global_fallback = bool(os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE_PATH"))

        if result.data:
            cred = result.data[0]
            return {
                "has_credentials": True,
                "credential_type": cred["credential_type"],
                "created_at": cred["created_at"],
                "last_used_at": cred["last_used_at"],
                "service_account_email": cred.get("service_account_email"),
                "fallback_available": global_fallback
            }
        else:
            return {
                "has_credentials": False,
                "credential_type": None,
                "fallback_available": global_fallback
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting calendar auth status: {e}")
        raise HTTPException(500, "Failed to get calendar auth status")


@app.post("/api/clients/{client_id}/calendar/oauth/initiate")
async def initiate_oauth_flow(
    client_id: str, token: str = Depends(get_current_user_token)
):
    """Initiate OAuth flow for Google Calendar authentication."""
    logger.info(f"=== OAUTH INITIATE ENDPOINT ===")
    logger.info(f"Client ID: {client_id}")
    try:
        logger.debug(f"Getting Supabase client...")
        supabase = get_supabase_client()
        if not supabase:
            logger.error("Supabase client is None")
            raise HTTPException(500, "Database unavailable")

        # Verify user owns this client
        logger.debug(f"Decoding JWT token...")
        user_id = jwt.decode(token, options={"verify_signature": False})["sub"]
        logger.debug(f"User ID from token: {user_id}")

        logger.debug(f"Getting client config for {client_id}...")
        client_data = await get_client_config(client_id)
        if not client_data:
            logger.error(f"Client not found: {client_id}")
            raise HTTPException(403, "Client not found")

        if client_data.get("owner_user_id") != user_id:
            logger.error(f"User {user_id} does not own client {client_id}")
            raise HTTPException(403, "Unauthorized")

        logger.info(f"Generating OAuth URL for client {client_id}...")
        # Generate OAuth URL
        authorization_url, state = generate_oauth_url(client_id, user_id, supabase)

        logger.info(f"OAuth URL generated successfully")
        return {
            "authorization_url": authorization_url,
            "state": state
        }

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"ValueError in OAuth initiate: {e}")
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Error initiating OAuth flow: {e}", exc_info=True)
        raise HTTPException(500, "Failed to initiate OAuth flow")


@app.get("/api/calendar/oauth/callback")
async def oauth_callback(
    code: str,
    state: str
):
    """Handle OAuth callback from Google."""
    try:
        supabase = get_supabase_client()
        if not supabase:
            return Response(
                content="<html><body><h1>Error</h1><p>Database unavailable</p></body></html>",
                media_type="text/html"
            )

        # Get client_id from state token
        state_record = supabase.table("oauth_state_tokens").select("client_id").eq("state", state).execute()
        if not state_record.data:
            return Response(
                content="<html><body><h1>Error</h1><p>Invalid state token</p></body></html>",
                media_type="text/html",
                status_code=400
            )

        client_id = state_record.data[0]["client_id"]

        # Handle OAuth callback
        result = await handle_oauth_callback(code, state, client_id, supabase)

        # Return HTML that closes the popup and notifies the parent window
        html_content = """
        <html>
        <head>
            <title>Authentication Successful</title>
            <style>
                body {
                    font-family: system-ui, -apple-system, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                }
                .container {
                    background: white;
                    padding: 2rem;
                    border-radius: 8px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                    text-align: center;
                }
                .success {
                    color: #10b981;
                    font-size: 3rem;
                    margin-bottom: 1rem;
                }
                h1 {
                    color: #1f2937;
                    margin: 0 0 0.5rem 0;
                }
                p {
                    color: #6b7280;
                    margin: 0;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success">✓</div>
                <h1>Authentication Successful</h1>
                <p>You can close this window now.</p>
            </div>
            <script>
                // Notify parent window and close popup
                if (window.opener) {
                    window.opener.postMessage({
                        type: 'oauth_success',
                        credential_type: '""" + result["credential_type"] + """'
                    }, '*');
                    setTimeout(() => window.close(), 2000);
                }
            </script>
        </body>
        </html>
        """

        return Response(content=html_content, media_type="text/html")

    except ValueError as e:
        error_html = f"""
        <html>
        <head><title>Authentication Error</title></head>
        <body>
            <h1>Authentication Error</h1>
            <p>{str(e)}</p>
            <p>You can close this window.</p>
        </body>
        </html>
        """
        return Response(content=error_html, media_type="text/html", status_code=400)
    except Exception as e:
        logger.error(f"Error in OAuth callback: {e}")
        error_html = f"""
        <html>
        <head><title>Authentication Error</title></head>
        <body>
            <h1>Authentication Error</h1>
            <p>An unexpected error occurred. Please try again.</p>
            <p>You can close this window.</p>
        </body>
        </html>
        """
        return Response(content=error_html, media_type="text/html", status_code=500)


@app.post("/api/clients/{client_id}/calendar/service-account")
async def upload_service_account_key(
    client_id: str,
    request: Request,
    token: str = Depends(get_current_user_token)
):
    """Upload service account JSON key for a client."""
    try:
        supabase = get_supabase_client()
        if not supabase:
            raise HTTPException(500, "Database unavailable")

        # Verify user owns this client
        user_id = jwt.decode(token, options={"verify_signature": False})["sub"]
        client_data = await get_client_config(client_id)
        if not client_data or client_data.get("owner_user_id") != user_id:
            raise HTTPException(403, "Unauthorized")

        # Get JSON from request body
        data = await request.json()
        service_account_json = data.get("service_account_json")

        if not service_account_json:
            raise HTTPException(400, "service_account_json is required")

        # Upload and store credentials
        result = await upload_service_account(
            client_id, user_id, service_account_json, supabase
        )

        return {
            "success": True,
            "credential_type": result["credential_type"],
            "service_account_email": result["service_account_email"]
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Error uploading service account: {e}")
        raise HTTPException(500, "Failed to upload service account")


@app.delete("/api/clients/{client_id}/calendar/credentials")
async def revoke_calendar_credentials(
    client_id: str, token: str = Depends(get_current_user_token)
):
    """Revoke calendar credentials for a client."""
    try:
        supabase = get_supabase_client()
        if not supabase:
            raise HTTPException(500, "Database unavailable")

        # Verify user owns this client
        user_id = jwt.decode(token, options={"verify_signature": False})["sub"]
        client_data = await get_client_config(client_id)
        if not client_data or client_data.get("owner_user_id") != user_id:
            raise HTTPException(403, "Unauthorized")

        # Revoke credentials
        success = await revoke_credentials(client_id, user_id, supabase)

        if success:
            return {"success": True, "message": "Credentials revoked"}
        else:
            raise HTTPException(500, "Failed to revoke credentials")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error revoking credentials: {e}")
        raise HTTPException(500, "Failed to revoke credentials")


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
    client_id = data.get("client_id", "")
    if not name or not client_id:
        raise HTTPException(400, "Name and client_id are required")
    success = await update_contact_name(phone, name, client_id)
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


@app.get("/api/templates")
async def get_templates():
    template_manager = app.state.template_manager
    return template_manager.get_all_templates()


@app.get("/api/admin/dashboard")
async def get_admin_dashboard(token: str = Depends(get_current_user_token)):
    """
    Secure Admin Endpoint.
    """
    # A. Define the Boss
    ADMIN_EMAIL = "admin@frontdesk.com"

    # B. Decode Token (without signature verification for robustness in dev)
    try:
        # We trust Supabase issued this token if we are on the same domain.
        # In production, you MUST verify the signature using your JWT Secret.
        payload = jwt.decode(token, options={"verify_signature": False})
        user_email = payload.get("email")

        logger.info(f"ADMIN CHECK: Request from {user_email}")

    except Exception as e:
        logger.error(f"Token Decode Error: {e}")
        raise HTTPException(status_code=401, detail="Invalid Token Format")

    # C. The Bouncer
    if user_email != ADMIN_EMAIL:
        logger.warning(f"Unauthorized admin access attempt by {user_email}")
        # 403 tells the frontend: "I know who you are, and you are NOT allowed."
        raise HTTPException(status_code=403, detail="Forbidden: Admins only.")

    # D. Grant Access (God Mode)
    # Uses Service Role to bypass RLS
    ledger = await get_admin_ledger()
    clients = await get_admin_clients()
    users = await get_admin_users()

    # Fetch and merge usage stats
    usage_stats = await get_client_usage_stats()

    # Initialize defaults for all clients first
    for client in clients:
        client["usage_today"] = 0
        client["usage_month"] = 0

    if usage_stats:
        usage_map = {
            stat["client_id"]: {
                "seconds_today": stat["seconds_today"],
                "seconds_month": stat["seconds_month"],
            }
            for stat in usage_stats
        }
        for client in clients:
            client_id = client.get("id")
            if client_id in usage_map:
                client["usage_today"] = usage_map[client_id]["seconds_today"]
                client["usage_month"] = usage_map[client_id]["seconds_month"]

    # FIX: Move this OUT of the if block and use 'or {}' to prevent NoneType error
    global_stats = await get_global_usage_stats() or {}

    return {
        "ledger": ledger,
        "clients": clients,
        "users": users,
        "total_seconds_today": global_stats.get("total_seconds_today", 0),
        "total_seconds_month": global_stats.get("total_seconds_month", 0),
    }


@app.post("/api/admin/adjust-balance")
async def admin_adjust_balance(
    request: AdjustBalanceRequest, token: str = Depends(get_current_user_token)
):
    """
    Secure Admin Endpoint to manually credit/debit client balance.
    """
    ADMIN_EMAIL = "admin@frontdesk.com"

    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        user_email = payload.get("email")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Token")

    if user_email != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Forbidden")

    success = await adjust_client_balance(
        request.client_id, request.amount_seconds, request.reason
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to adjust balance")

    return {"message": "Balance adjusted successfully"}


@app.get("/api/admin/client/{client_id}/ledger")
async def admin_get_client_ledger(
    client_id: str, token: str = Depends(get_current_user_token)
):
    """
    Secure Admin Endpoint to fetch client specific ledger.
    """
    ADMIN_EMAIL = "admin@frontdesk.com"

    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        user_email = payload.get("email")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Token")

    if user_email != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Forbidden")

    ledger = await get_client_ledger(client_id)
    return {"ledger": ledger}


@app.post("/api/admin/user/{user_id}/toggle-status")
async def admin_toggle_user_status(
    user_id: str, token: str = Depends(get_current_user_token)
):
    """
    Secure Admin Endpoint to toggle user active status.
    """
    ADMIN_EMAIL = "admin@frontdesk.com"

    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        user_email = payload.get("email")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Token")

    if user_email != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Forbidden")

    new_status = await toggle_user_status(user_id)

    if new_status is None:
        raise HTTPException(status_code=500, detail="Failed to toggle status")

    return {"is_active": new_status}


@app.put("/api/admin/client/{client_id}")
async def admin_update_client_endpoint(
    client_id: str,
    client_data: AdminClientUpdate,
    token: str = Depends(get_current_user_token),
):
    """
    Secure Admin Endpoint to update client configuration.
    """
    ADMIN_EMAIL = "admin@frontdesk.com"

    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        user_email = payload.get("email")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Token")

    if user_email != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Filter out None values
    data = {k: v for k, v in client_data.dict().items() if v is not None}

    updated_client = await admin_update_client(client_id, data)

    if not updated_client:
        raise HTTPException(status_code=500, detail="Failed to update client")

    return updated_client


@app.get("/api/admin/conversation/{conversation_id}")
async def admin_get_conversation(
    conversation_id: str, token: str = Depends(get_current_user_token)
):
    """
    Secure Admin Endpoint to fetch full conversation details.
    """
    ADMIN_EMAIL = "admin@frontdesk.com"

    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        user_email = payload.get("email")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Token")

    if user_email != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Forbidden")

    conversation = await get_conversation_by_id(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return conversation


@app.get("/api/admin/active-calls")
async def admin_get_active_calls(token: str = Depends(get_current_user_token)):
    """
    Secure Admin Endpoint to see all active calls in real-time.
    """
    ADMIN_EMAIL = "admin@frontdesk.com"
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        user_email = payload.get("email")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Token")

    if user_email != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Forbidden")

    return list(active_calls.values())


@app.get("/api/admin/analytics")
async def get_analytics(token: str = Depends(get_current_user_token)):
    """
    Admin endpoint for daily financial analytics (Cost vs Revenue).
    """
    ADMIN_EMAIL = "admin@frontdesk.com"

    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        user_email = payload.get("email")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Token")

    if user_email != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Forbidden")

    data = await get_financial_history(30)
    return data


@app.get("/api/admin/analytics/by-service")
async def get_analytics_by_service(
    days: int = 30,
    token: str = Depends(get_current_user_token)
):
    """
    Admin endpoint for cost breakdown by service/metric type.
    """
    ADMIN_EMAIL = "admin@frontdesk.com"

    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        user_email = payload.get("email")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Token")

    if user_email != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Forbidden")

    data = await get_cost_by_service(days)
    return data


@app.get("/api/admin/analytics/by-client")
async def get_analytics_by_client(
    days: int = 30,
    token: str = Depends(get_current_user_token)
):
    """
    Admin endpoint for cost breakdown by client (profitability).
    """
    ADMIN_EMAIL = "admin@frontdesk.com"

    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        user_email = payload.get("email")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Token")

    if user_email != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Forbidden")

    data = await get_cost_by_client(days)
    return data


@app.get("/api/admin/analytics/top-calls")
async def get_analytics_top_calls(
    limit: int = 10,
    token: str = Depends(get_current_user_token)
):
    """
    Admin endpoint for most expensive calls.
    """
    ADMIN_EMAIL = "admin@frontdesk.com"

    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        user_email = payload.get("email")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Token")

    if user_email != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Forbidden")

    data = await get_top_expensive_calls(limit)
    return data


@app.get("/api/admin/balances")
async def get_admin_balances(token: str = Depends(get_current_user_token)):
    """
    Secure Admin Endpoint to fetch service balances.
    """
    ADMIN_EMAIL = "admin@frontdesk.com"
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        user_email = payload.get("email")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Token")

    if user_email != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Forbidden")

    return await get_service_balances()


@app.get("/api/admin/settings")
async def get_admin_settings(token: str = Depends(get_current_user_token)):
    """
    Secure Admin Endpoint to fetch system rates.
    """
    ADMIN_EMAIL = "admin@frontdesk.com"
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        user_email = payload.get("email")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Token")

    if user_email != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Forbidden")

    return await get_system_rates()


@app.post("/api/admin/settings")
async def update_admin_setting(
    request: UpdateSystemRateRequest, token: str = Depends(get_current_user_token)
):
    """
    Secure Admin Endpoint to update a system rate.
    """
    ADMIN_EMAIL = "admin@frontdesk.com"
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        user_email = payload.get("email")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Token")

    if user_email != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Forbidden")

    success = await update_system_rate(request.key, request.value)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update setting")
    return {"message": "Setting updated", "key": request.key, "value": request.value}


@app.get("/api/active-calls")
async def get_user_active_calls(token: str = Depends(get_current_user_token)):
    """
    Get active calls for the current user's clients.
    """
    supabase = get_supabase_client()
    try:
        user = supabase.auth.get_user(token)
        if not user or not user.user:
            raise HTTPException(status_code=401, detail="Invalid Token")
        user_id = user.user.id
    except Exception as e:
        logger.error(f"Auth error: {e}")
        raise HTTPException(status_code=401, detail="Invalid Token")

    # Filter calls owned by this user
    user_calls = [
        call for call in active_calls.values() if call.get("owner_user_id") == user_id
    ]
    return user_calls


# Define Price IDs
PRICE_IDS = {
    "starter": os.environ.get("STRIPE_PRICE_STARTER"),
    "growth": os.environ.get("STRIPE_PRICE_GROWTH"),
    "power": os.environ.get("STRIPE_PRICE_POWER"),
}

TOPUP_IDS = {
    "topup_small": os.environ.get("STRIPE_TOPUP_SMALL"),
    "topup_medium": os.environ.get("STRIPE_TOPUP_MEDIUM"),
    "topup_large": os.environ.get("STRIPE_TOPUP_LARGE"),
}


@app.post("/api/billing/create-checkout-session")
async def create_checkout_session(request: CheckoutSessionRequest):
    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

    # Subscription Packages
    subscriptions = {
        "starter": {"seconds": 6000, "name": "Starter Pack (100 mins)"},
        "growth": {"seconds": 18000, "name": "Growth Pack (300 mins)"},
        "power": {"seconds": 42000, "name": "Power Pack (700 mins)"},
    }

    # One-Time Top-Ups
    topups = {
        "topup_small": {"seconds": 3000, "name": "Refuel 50 (50 mins)"},
        "topup_medium": {"seconds": 6000, "name": "Refuel 100 (100 mins)"},
        "topup_large": {"seconds": 30000, "name": "Refuel 500 (500 mins)"},
    }

    # Determine Mode & Package
    mode = "subscription"
    price_id = PRICE_IDS.get(request.package_id)
    package = subscriptions.get(request.package_id)

    if not price_id:
        # Check Top-Ups
        price_id = TOPUP_IDS.get(request.package_id)
        package = topups.get(request.package_id)
        mode = "payment"

    if not package or not price_id:
        raise HTTPException(status_code=400, detail="Invalid package ID")

    try:
        # Get base URL for success/cancel redirects
        base_url = os.environ.get("BASE_URL", "http://localhost:8000")

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price": price_id,
                    "quantity": 1,
                }
            ],
            mode=mode,
            metadata={
                "client_id": request.client_id,
                "add_seconds": str(package["seconds"]),  # Kept for webhook simplicity
                "package_id": request.package_id,
            },
            success_url=f"{base_url}/static/index.html?payment=success",
            cancel_url=f"{base_url}/static/index.html?payment=cancelled",
        )

        return {"url": session.url}

    except Exception as e:
        logger.error(f"Stripe checkout creation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/billing/webhook")
async def stripe_webhook(request: Request):
    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    event = None

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except ValueError:
        # Invalid payload
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        # Invalid signature
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Handle the event
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]

        # Fulfill the purchase...
        client_id = session["metadata"].get("client_id")
        add_seconds = session["metadata"].get("add_seconds")

        if client_id and add_seconds:
            try:
                seconds = int(add_seconds)
                # Extract revenue from Stripe session (amount_total is in cents)
                revenue_usd = session.get("amount_total", 0) / 100.0
                logger.info(
                    f"STRIPE WEBHOOK: Adding {seconds}s to client {client_id} for ${revenue_usd}"
                )
                await adjust_client_balance(
                    client_id, seconds, "STRIPE_TOPUP", revenue_usd
                )
            except Exception as e:
                logger.error(f"Error processing stripe fulfillment: {e}")
                return Response(status_code=500)

    return {"status": "success"}


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-mode", action="store_true")
    args = parser.parse_args()

    runner = PipelineRunner()
    template_manager = TemplateManager()
    shutdown_event = asyncio.Event()

    app.state.runner = runner
    app.state.template_manager = template_manager
    app.state.test_mode = args.test_mode
    app.state.shutdown_event = shutdown_event

    # Sync pricing data on startup
    logging.info("Syncing OpenRouter pricing data...")
    try:
        await sync_openrouter_prices()
        logging.info("Pricing data synced successfully.")
    except Exception as e:
        logging.warning(f"Failed to sync pricing data: {e}. Continuing without price sync.")

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
