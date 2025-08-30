import httpx
from chatling import get_chatling_response
import logging

logger = logging.getLogger("bitrix")

# Permanent webhook URL
BITRIX_WEBHOOK_URL = "https://finideas.bitrix24.in/rest/24/79r2m74ous5yme5r/"

# Bot credentials
BOT_ID = 77148
CLIENT_ID = "jdg3syzhve9ve7vv93dv4y3gs5bc31mo"

async def handle_bitrix_event(event: str, dialog_id: str, message: str, user_id: str = None):
    """
    Process Bitrix event: forward user message to Chatling, get reply, 
    then send reply back into the chat.
    """
    if event == "ONIMBOTMESSAGEADD" and dialog_id and message:
        reply = await get_chatling_response(message, bitrix_dialog_id=dialog_id, user_id=user_id)
        await send_message_to_bitrix(dialog_id, reply)
        return {"status": "ok", "reply": reply}

    return {"status": "ignored"}

async def send_message_to_bitrix(dialog_id: str, message: str):
    """
    Send bot message back to Bitrix chat.
    """
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
            logger.info(f"Sent to Bitrix response: {data}")
        except httpx.HTTPStatusError as e:
            logger.error(f"Bitrix API error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            logger.error(f"Unexpected error sending to Bitrix: {str(e)}")
