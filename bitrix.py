import httpx
from chatling import get_chatling_response
import logging
import sys
import re
import os
import json
from typing import Optional

logger = logging.getLogger("bitrix")

BITRIX_WEBHOOK_URL = os.environ.get("BITRIX_WEBHOOK_URL")

BOT_ID = os.environ.get("BOT_ID")
CLIENT_ID = os.environ.get("CLIENT_ID")


# Setup logger
logging.basicConfig(
    filename="bitrix.log",
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

async def update_lead_field(lead_id: str, field_name: str, value) -> bool:
    """
    Update a custom field in a Bitrix24 lead.
    """
    url = f"{BITRIX_WEBHOOK_URL}/crm.lead.update.json"
    payload = {
        "id": lead_id,
        "fields": {
            field_name: value
        }
    }

    logging.debug(f"Updating lead → {lead_id}, field → {field_name}, value → {value}")
    logging.debug(f"Payload being sent → {payload}")



    async with httpx.AsyncClient() as client:
        try:
            res = await client.post(url, json=payload)
            logging.debug(f"Bitrix response status → {res.status_code}")
            logging.debug(f"Bitrix response body → {res.text}")
            res.raise_for_status()
            data = res.json()
            if "error" in data:
                print("Bitrix API Error:", data["error_description"])
                return False
            return data.get("result", False)
        except Exception as e:
            logging.error(f"Error updating lead {lead_id}: {e}")
            return False

def clean_message_for_bitrix(message: str) -> str:
    """
    Convert markdown-style links from Chatling into plain clickable URLs
    so Bitrix can display them correctly.
    """
    # Replace [text](url) → url
    message = re.sub(r'\[([^\]]+)\]\((https?://[^\)]+)\)', r'\2', message)
    
    # Optional: strip extra spaces/newlines
    message = message.strip()
    return message


async def handle_bitrix_event(event: str, dialog_id: str, message: str, user_id: str = None,bitrix_user_info: dict = None,    instructions: Optional[list[str]] = None):
 
    if event == "ONIMBOTMESSAGEADD" and dialog_id and  (message or instructions):
       
        reply = await get_chatling_response(user_message = message, bitrix_dialog_id=dialog_id, user_id=user_id,bitrix_user_info= bitrix_user_info,instructions=instructions)
        cleaned_response = clean_message_for_bitrix(reply)
        await send_message_to_bitrix(dialog_id, cleaned_response)
        return {"status": "ok", "reply": reply}

    return {"status": "ignored"}

async def send_message_to_bitrix(dialog_id: str, message: str):

    logger.info(f"Sending to Bitrix: dialog_id={dialog_id}, message={message}")
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{BITRIX_WEBHOOK_URL}imbot.message.add.json",
                json={
                    "BOT_ID": BOT_ID,
                    "CLIENT_ID": CLIENT_ID,
                    "DIALOG_ID": dialog_id,
                    "MESSAGE": message
                }
            )
            response.raise_for_status()
            logger.info(f"Sent to Bitrix response: {response.json()}")
        except httpx.HTTPStatusError as e:
            logger.error(f"Bitrix API error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            logger.error(f"Unexpected error sending to Bitrix: {str(e)}")
