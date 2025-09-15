from fastapi import FastAPI, Request
from urllib.parse import parse_qs
import logging
from dotenv import load_dotenv
from bitrix import handle_bitrix_event, update_lead_field
import sys
from supabase import create_client
from datetime import datetime, timezone
import os

load_dotenv()

# ✅ Initialize Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
# Load from environment with defaults
MESSAGE_TIMEOUT_MINUTES = int(os.getenv("MESSAGE_TIMEOUT_MINUTES", "60"))
MONITOR_SLEEP_SECONDS = int(os.getenv("MONITOR_SLEEP_SECONDS", "60"))



if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY in environment")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

from contextlib import asynccontextmanager

# 🟢 Define lifespan context
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    asyncio.create_task(monitor_pending_messages())
    logger.info("Background task for monitoring pending_messages started")

    yield  # 👈 this is where the app runs

    # Shutdown logic (optional)
    logger.info("Shutting down app...")


# 🟢 Initialize FastAPI with lifespan
app = FastAPI(lifespan=lifespan)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger("bitrix-handler")


logger.info(
    f"Monitor configured with timeout={MESSAGE_TIMEOUT_MINUTES} minutes, "
    f"sleep={MONITOR_SLEEP_SECONDS} seconds"
)

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
    user_name = parsed.get("data[USER][NAME]", [None])[0]
    first_name = parsed.get("data[USER][FIRST_NAME]", [None])[0]
    last_name = parsed.get("data[USER][LAST_NAME]", [None])[0]
    email = parsed.get("data[USER][EMAIL]", [None])[0]   # if provided by Bitrix
    phone = parsed.get("data[USER][PHONE]", [None])[0]   # if provided by Bitrix

    logger.info(f"Event: {event}, Message: {message}, Dialog ID: {dialog_id}, User ID: {user_id}")

        # 🔹 Extract LEAD ID from CHAT_ENTITY_DATA_1
    chat_entity_data = parsed.get("data[PARAMS][CHAT_ENTITY_DATA_1]", [None])[0]
    lead_id = None
    if chat_entity_data:
        parts = chat_entity_data.split("|")
        if len(parts) > 2 and parts[1] == "LEAD":
            lead_id = parts[2]  # 558568

    logger.info(f"Event: {event}, Message: {message}, Dialog ID: {dialog_id}, Lead ID: {lead_id}")

    # 🔹 If we have a lead, update the custom True/False field
    if lead_id:
        await update_lead_field(lead_id, "UF_CRM_1592568003637", 1)

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
        
            # 🟢 If message is from INTERNAL USER (work_position present, not HiddenMessage)
        if work_position and component_id != "HiddenMessage":
            logger.info(f"Internal user {user_id} responded in dialog {dialog_id} with message: {message!r}")

            try:
                # fetch latest pending_messages row for this dialog
                existing_pm = supabase.table("pending_messages") \
                    .select("id, created_at, message") \
                    .eq("dialog_id", dialog_id) \
                    .eq("flushed", False) \
                    .order("created_at", desc=True) \
                    .limit(1) \
                    .execute()

                logger.info(f"Latest pending_messages for {dialog_id}: {existing_pm.data}")

                if existing_pm.data:
                    record_id = existing_pm.data[0]["id"]
                    # new_time = datetime.now(timezone.utc).isoformat()

                    # delete pending_message record
                    delete_resp = supabase.table("pending_messages") \
                        .delete() \
                        .eq("id", record_id) \
                        .execute()

                    logger.info(
                        f"Deleted pending_messages id={record_id}. "
                        f"Delete response: {delete_resp.data}"
                    )
                else:
                    logger.info(f"No pending_messages found for dialog {dialog_id}, nothing to reset")

            except Exception as e:
                logger.error(f"Error resetting created_at for dialog {dialog_id}: {str(e)}")

            return {"status": "ok", "action": "reset timer"}

        # Check if record exists
        existing = supabase.table("chat_mapping").select("*").eq("bitrix_dialog_id", dialog_id).execute()

        if not existing.data:  # no record found → insert
            logger.info(f"No record found for dialog {dialog_id}, inserting new mapping...")
            supabase.table("chat_mapping").insert({
                "bitrix_dialog_id": dialog_id,
                "chatling_conversation_id": None,  # will be filled later
                "name": user_name or f"{first_name} {last_name}".strip(),
                "phone": phone,
                "email": email,
                "chat_status": "active"
            }).execute()
            chat_status = "active"
        else:  # record exists → reuse it
            chat_status = existing.data[0].get("chat_status", "active")


        if chat_status == "stopped":
            logger.info(f"Chat {dialog_id} is in STOPPED mode, ignoring message")
                    # 🔹 Store / Append to pending_messages
        # 🔹 Store / Append to pending_messages
            try:
                existing_pm = supabase.table("pending_messages") \
                    .select("id,message") \
                    .eq("dialog_id", dialog_id) \
                    .eq("flushed", False) \
                    .limit(1) \
                    .execute()

                logger.info(f"Fetched existing pending_messages for {dialog_id}: {existing_pm.data}")

                if not existing_pm.data:
                    # No record yet → insert new one
                    supabase.table("pending_messages").insert({
                        "dialog_id": dialog_id,
                        "user_id": user_id,
                        "message": message
                    }).execute()
                    logger.info(f"Inserted new pending_messages row for dialog {dialog_id} with message: {message}")
                else:
                    record = existing_pm.data[0]
                    record_id = record["id"]
                    old_msg = record.get("message") or ""
                    logger.info(f"Existing message for dialog {dialog_id} (id={record_id}): {old_msg!r}")

                    new_msg = (old_msg + "\n" + message).strip()
                    logger.info(f"Appending new message. Combined message for dialog {dialog_id}: {new_msg!r}")

                    update_resp = supabase.table("pending_messages") \
                        .update({"message": new_msg}) \
                        .eq("id", record_id) \
                        .execute()

                    logger.info(f"Update response from Supabase: {update_resp.data}")

            except Exception as e:
                logger.error(f"Error storing pending_messages for dialog {dialog_id}: {str(e)}")

            return {"status": "ignored", "reason": "auto stopped"}

        # # 🔹 NEW: skip internal users
        # if work_position:
        #     logger.info(
        #         f"Skipping Chatling call because message is from internal user {user_id} (position: {work_position})"
        #     )
        #     return {"status": "ignored", "reason": "internal user"}
        
        # Optional: filter for specific keywords
        # if "hello chatbot" in message.lower():
        logger.info(f"Processing message for dialog {dialog_id}")
        try:
            response = await handle_bitrix_event(
                event=event,
                dialog_id=dialog_id,
                message=message,
                user_id=user_id,
                bitrix_user_info=parsed
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

import asyncio
from datetime import datetime, timedelta, timezone

BOT_PROMPT_consolidate = """The user sent the following messages, which were delayed in reaching you. 
Please read them all together and reply in a single, coherent response. 
Begin your reply with a brief apology for the delay. 
Do not answer each message individually.
"""



# 🟢 Background task to check pending messages
async def monitor_pending_messages():
    while True:
        try:
            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(minutes=MESSAGE_TIMEOUT_MINUTES)
            cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S%z")
            logger.info(f"Cutoff: {cutoff} ({cutoff_str})")


            # Fetch all messages older than 60 mins
            result = supabase.table("pending_messages") \
                .select("id, dialog_id, message, created_at") \
                .eq("flushed", False) \
                .lte("created_at", cutoff_str) \
                .execute()
            
            # logger.info(f"Escalating dialog {dialog_id} (msg_id={msg_id}) with message={message!r} to Chatling.ai")


            if result.data:
                logger.info(f"Found {len(result.data)} pending_messages older than {MESSAGE_TIMEOUT_MINUTES} mins")

                messages_to_send = []

                for row in result.data:
                    dialog_id = row["dialog_id"]
                    msg_id = row["id"]
                    message = row["message"]

                    # 🔹 Only process chat72172
                    if dialog_id != "chat72172":
                        logger.info(f"Skipping dialog {dialog_id}, only monitoring chat72172")
                        continue
                    
                    messages_to_send.append(message)

                    if messages_to_send:
                        combined_message = BOT_PROMPT_consolidate + "\n\n" + "\n".join(messages_to_send)
                    logger.info(f"Escalating dialog {dialog_id} (msg_id={msg_id}) to Chatling.ai")

                    try:
                        # 🔹 Send to Chatling.ai
                        response = await handle_bitrix_event(
                            event="ONIMBOTMESSAGEADD",
                            dialog_id=dialog_id,
                            message=combined_message,
                            user_id="system",   # system trigger
                            bitrix_user_info={}
                        )
                        logger.info(f"Chatling response: {response}")

                        # 🔹 Mark chat as active again
                        supabase.table("chat_mapping") \
                            .update({"chat_status": "active"}) \
                            .eq("bitrix_dialog_id", dialog_id) \
                            .execute()

                        # 🔹 Delete the pending message record
                        supabase.table("pending_messages") \
                            .delete() \
                            .eq("id", msg_id) \
                            .execute()

                        logger.info(f"Dialog {dialog_id}: set ACTIVE + deleted pending_messages id={msg_id}")

                    except Exception as e:
                        logger.error(f"Error escalating dialog {dialog_id}: {str(e)}")

            else:
                logger.info("No pending_messages older than {MESSAGE_TIMEOUT_MINUTES} mins found")

        except Exception as e:
            logger.error(f"Error in monitor_pending_messages: {str(e)}")

        await asyncio.sleep(MONITOR_SLEEP_SECONDS)  # check every 1 min



