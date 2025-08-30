from fastapi import FastAPI, Request
from urllib.parse import parse_qs
import logging
from dotenv import load_dotenv
from bitrix import handle_bitrix_event
import sys
from supabase import create_client
import os

load_dotenv()

# ✅ Initialize Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY in environment")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger("bitrix-handler")


@app.post("/bitrix-handler")
async def bitrix_webhook(request: Request):
    # Read and parse request
    body_bytes = await request.body()
    body_str = body_bytes.decode("utf-8", errors="replace")
    logger.info(f"Raw body from Bitrix: {body_str}")

    parsed = parse_qs(body_str)
    logger.info(f"Parsed form data from Bitrix: {parsed}")

    # Extract core fields
    event = parsed.get("event", [""])[0]
    message = parsed.get("data[PARAMS][MESSAGE]", [""])[0].strip()
    dialog_id = parsed.get("data[PARAMS][DIALOG_ID]", [""])[0]
    user_id = parsed.get("data[PARAMS][FROM_USER_ID]", [""])[0]
    work_position = parsed.get("data[USER][WORK_POSITION]", [None])[0]

    logger.info(f"Event: {event}, Message: {message}, Dialog ID: {dialog_id}, User ID: {user_id}")

        # 🔹 Detect HiddenMessage (whisper mode)
    component_id = parsed.get("data[PARAMS][PARAMS][COMPONENT_ID]", [""])[0]
    if component_id == "HiddenMessage":
        if message.lower() == "stop auto":
            supabase.table("chat_mapping").update({"chat_status": "stopped"}).eq("bitrix_dialog_id", dialog_id).execute()
            logger.info(f"Chat {dialog_id} set to STOPPED")
            return {"status": "ok", "action": "stop auto"}
        elif message.lower() == "start auto":
            supabase.table("chat_mapping").update({"chat_status": "active"}).eq("bitrix_dialog_id", dialog_id).execute()
            logger.info(f"Chat {dialog_id} set to ACTIVE")
            return {"status": "ok", "action": "start auto"}
        else:
            logger.info(f"Ignored hidden message: {message}")
            return {"status": "ignored", "reason": "other hidden message"}

    # Handle only real messages
    if event == "ONIMBOTMESSAGEADD":
        if not message:
            logger.info(f"Ignoring ONIMBOTMESSAGEADD with empty message for dialog {dialog_id}")
            return {"status": "ignored", "reason": "empty message"}
        
        # Check if auto mode stopped
        record = supabase.table("chat_mapping").select("chat_status").eq("bitrix_dialog_id", dialog_id).execute()
        chat_status = record.data[0]["chat_status"] if record.data else "active"

        if chat_status == "stopped":
            logger.info(f"Chat {dialog_id} is in STOPPED mode, ignoring message")
            return {"status": "ignored", "reason": "auto stopped"}

        # 🔹 NEW: skip internal users
        if work_position:
            logger.info(
                f"Skipping Chatling call because message is from internal user {user_id} (position: {work_position})"
            )
            return {"status": "ignored", "reason": "internal user"}
        
        # Optional: filter for specific keywords
        # if "hello chatbot" in message.lower():
        logger.info(f"Processing message for dialog {dialog_id}")
        try:
            response = await handle_bitrix_event(
                event=event,
                dialog_id=dialog_id,
                message=message,
                user_id=user_id
            )
            return response
        except Exception as e:
            logger.error(f"Error handling Bitrix event: {str(e)}")
            return {"status": "error", "reason": str(e)}
    # else:
        #     logger.info(f"Message ignored due to keyword filter: {message}")
        #     return {"status": "ignored", "reason": "keyword not found"}

    # Ignore non-message events
    logger.info(f"Ignoring non-message event {event} for dialog {dialog_id}")
    return {"status": "ignored", "reason": "non-message event or empty message"}


@app.get("/")
def health():
    return {"status": "alive"}
