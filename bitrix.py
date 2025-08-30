import httpx
from chatling import get_chatling_response

# ✅ Permanent webhook URL
BITRIX_WEBHOOK_URL = "https://finideas.bitrix24.in/rest/24/79r2m74ous5yme5r/"

# ✅ Your Bot credentials
BOT_ID = 77148   # Replace with your actual bot ID
CLIENT_ID = "jdg3syzhve9ve7vv93dv4y3gs5bc31mo"  # From Bitrix24 bot settings

async def handle_bitrix_event(event: str, dialog_id: str, message: str):
    """
    Process Bitrix event: forward user message to Chatling, get reply, 
    then send reply back into the chat.
    """
    if event == "ONIMBOTMESSAGEADD" and dialog_id and message:
        reply = await get_chatling_response(message, session_id=dialog_id)
        await send_message_to_bitrix(dialog_id, reply)
        return {"status": "ok", "reply": reply}

    return {"status": "ignored"}

async def send_message_to_bitrix(dialog_id: str, message: str):
    """
    Send bot message back to Bitrix chat.
    """
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
            print("✅ Sent to Bitrix:", response.json())
        except httpx.HTTPStatusError as e:
            print(f"Bitrix API error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            print(f"Unexpected error sending to Bitrix: {str(e)}")
