import os
import asyncio
import logging
import argparse
import signal
import urllib.parse
from dotenv import load_dotenv
import jwt

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
)

# Import tool handlers
from services.llm_tools import (
    handle_get_available_slots,
    handle_book_appointment,
    handle_save_contact_name,
    handle_reschedule_appointment,
    handle_cancel_appointment,
    handle_list_my_appointments,
)

# Import Google Calendar functions
from services.google_calendar import get_upcoming_appointments

# Import Response Filter
from services.response_filter import ToolStrippingAssistantAggregator

# Import Template Manager
from services.template_manager import TemplateManager

from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Connect, Stream


# Load environment variables
load_dotenv()

# Initialize Twilio Client
twilio_client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])

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

# --- Global State ---
active_calls = {}  # call_id -> { client_id, client_name, caller_phone, start_time, owner_user_id }
# --------------------

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


async def initialize_client_services(client_id: str, caller_phone: Optional[str] = None):
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
    tts_model = client_config.get("tts_model", "eleven_flash_v2_5")
    tts_voice_id = client_config.get("tts_voice_id", "21m00Tcm4TlvDq8ikWAM")
    initial_greeting = client_config.get("initial_greeting")

    enabled_tools = client_config.get("enabled_tools") or [
        "get_available_slots", "book_appointment", "save_contact_name",
        "reschedule_appointment", "cancel_appointment"
    ]

    stt = DeepgramSTTService(
        api_key=os.environ["DEEPGRAM_API_KEY"],
        model=stt_model,
        vad_events=True,
    )

    tts = ElevenLabsTTSService(
        api_key=os.environ["ELEVENLABS_API_KEY"],
        voice_id=tts_voice_id,
        model_id=tts_model,
        optimize_streaming_latency=4,
    )

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
            audio_in_sample_rate=8000,
            audio_out_sample_rate=8000,
            enable_metrics=True,
        ),
    )

    # --- Initial Greeting ---
    if initial_greeting:
        parts = initial_greeting.split(".", 1)
        if len(parts) == 2:
            await task.queue_frames(
                [TextFrame(parts[0].strip() + "."), TextFrame(parts[1].strip())]
            )
        else:
            await task.queue_frames([TextFrame(initial_greeting)])

    runner_task = asyncio.create_task(runner.run(task))

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
            # 3. ENFORCE: Hard Cutoff
            elapsed = (datetime.datetime.now() - call_start_time).total_seconds()
            if elapsed > balance_seconds:
                logger.warning(f"CUTOFF: Client {client_id} out of funds.")
                await websocket.close(code=4002, reason="Time Limit Exceeded")
                break
            await asyncio.sleep(0.1)
    except asyncio.CancelledError:
        pass
    finally:
        # --- Cleanup Active Call ---
        active_calls.pop(call_id, None)
        # ---------------------------

        safety_task.cancel()

        # 4. COMMIT: Finalize Billing
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
                msg_tool_calls = message.get("tool_calls") # 2. Extract from dict
            else:
                if getattr(message, "role", "") == "system":
                    continue
                msg_role = getattr(message, "role", "")
                msg_content = getattr(message, "content", "")
                msg_tool_calls = getattr(message, "tool_calls", None) # 3. Extract from object

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
            await log_usage_ledger(
                client_id,
                actual_conv_id,
                {
                    "call_duration": total_seconds,
                    "llm_tokens_input": input_tokens,
                    "llm_tokens_output": output_tokens,
                    "tts_characters": tts_chars,
                },
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


@app.get("/api/twilio/available-numbers")
async def get_available_numbers(area_code: str, token: str = Depends(get_current_user_token)):
    try:
        numbers = twilio_client.available_phone_numbers('US').local.list(
            area_code=area_code, limit=5
        )
        return {"numbers": [n.phone_number for n in numbers]}
    except Exception as e:
        logger.error(f"Twilio search error: {e}")
        # Return empty list or 500? Returning empty list is safer for UI, but 500 indicates failure.
        # Using 400 for bad request if area code is invalid, else 500.
        # Simple approach:
        raise HTTPException(status_code=400, detail=f"Failed to search numbers: {str(e)}")


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
    # 1. Handle Number Provisioning
    if client.selected_number:
        try:
            # Determine Voice URL (Webhook)
            # In production, use your real domain. For dev, we assume BASE_URL is set or use a placeholder.
            # Ideally, the user sets BASE_URL in .env
            base_url = os.environ.get("BASE_URL")
            if not base_url:
                 # Fallback for safety, but this might not work for callbacks
                 logger.warning("BASE_URL not set. Twilio Voice URL might be incorrect.")
                 base_url = "https://example.com" 
            
            webhook_url = f"{base_url}/voice"

            purchased_number = twilio_client.incoming_phone_numbers.create(
                phone_number=client.selected_number,
                voice_url=webhook_url
            )
            
            # Override the cell field with the actually purchased number
            client.cell = purchased_number.phone_number
            logger.info(f"Provisioned Twilio Number: {client.cell}")
            
        except Exception as e:
            logger.error(f"Twilio Provisioning Failed: {e}")
            raise HTTPException(status_code=400, detail=f"Failed to purchase number: {str(e)}")

    # 2. Create DB Record
    new_client = await create_client_record(client.dict(exclude={'selected_number'}), token)
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
    # 1. Fetch client data to get the phone number
    client_data = await get_client_config(client_id)
    
    # 2. Release Twilio Number if it exists
    if client_data and client_data.get("cell"):
        release_twilio_number(client_data["cell"])

    # 3. Proceed with database deletion
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

    return {"ledger": ledger, "clients": clients, "users": users}


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
    client_id: str, client_data: AdminClientUpdate, token: str = Depends(get_current_user_token)
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
        call for call in active_calls.values() 
        if call.get("owner_user_id") == user_id
    ]
    return user_calls


@app.post("/api/billing/create-checkout-session")
async def create_checkout_session(request: CheckoutSessionRequest):
    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
    
    # Define packages
    packages = {
        "starter": {"amount": 2000, "seconds": 6000, "name": "Starter Pack (100 mins)"},
        "growth": {"amount": 5000, "seconds": 18000, "name": "Growth Pack (300 mins)"},
        "power": {"amount": 10000, "seconds": 42000, "name": "Power Pack (700 mins)"},
    }
    
    package = packages.get(request.package_id)
    if not package:
        raise HTTPException(status_code=400, detail="Invalid package ID")
        
    try:
        # Get base URL for success/cancel redirects
        # In production, this should be configured. For now, we infer from request or env
        # But since this is called from frontend, we can hardcode the path relative to where frontend is served
        # or use a configured BASE_URL env var.
        base_url = os.environ.get("BASE_URL", "http://localhost:8000")
        
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": package["name"],
                    },
                    "unit_amount": package["amount"],
                },
                "quantity": 1,
            }],
            mode="payment",
            metadata={
                "client_id": request.client_id,
                "add_seconds": str(package["seconds"]),
                "package_id": request.package_id
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
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
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
                logger.info(f"STRIPE WEBHOOK: Adding {seconds}s to client {client_id}")
                await adjust_client_balance(client_id, seconds, "STRIPE_TOPUP")
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
