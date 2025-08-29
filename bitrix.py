import httpx
from chatling import get_chatling_response
from utils import get_bot_token

BITRIX_WEBHOOK_URL = "https://finideas.bitrix24.in/rest"

async def handle_bitrix_event(payload):
    event = payload.get("event")
    dialog_id = payload.get("data", {}).get("PARAMS", {}).get("DIALOG_ID")
    message = payload.get("data", {}).get("PARAMS", {}).get("MESSAGE")
    auth_token = payload.get("auth", {}).get("application_token")

    if event == "ONIMBOTMESSAGEADD":
        # Use dialog_id as session_id for Chatling context continuity
        reply = await get_chatling_response(message, session_id=dialog_id)
        await send_message_to_bitrix(dialog_id, reply, auth_token)
        return {"status": "ok"}

    return {"status": "ignored"}

async def send_message_to_bitrix(dialog_id, message, auth_token):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{BITRIX_WEBHOOK_URL}/imbot.message.add",
                params={"auth": auth_token},
                data={
                    "BOT_ID": get_bot_token(),
                    "DIALOG_ID": dialog_id,
                    "MESSAGE": message
                }
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            print(f"Bitrix API error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            print(f"Unexpected error sending to Bitrix: {str(e)}")
