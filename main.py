from fastapi import FastAPI, Request
from urllib.parse import parse_qs
import logging
from dotenv import load_dotenv
from bitrix import handle_bitrix_event, update_lead_field
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
                    new_time = datetime.now(timezone.utc).isoformat()

                    # update created_at to internal user response time
                    update_resp = supabase.table("pending_messages") \
                        .update({"created_at": new_time}) \
                        .eq("id", record_id) \
                        .execute()

                    logger.info(
                        f"Updated created_at for pending_messages id={record_id} "
                        f"to {new_time}. Update response: {update_resp.data}"
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


            except Exception as e:
                logger.error(f"Error storing pending_messages: {str(e)}")

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
