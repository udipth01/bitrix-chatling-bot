import httpx
from chatling import get_chatling_response
from utils import get_bot_token

BITRIX_WEBHOOK_URL = "https://finideas.bitrix24.com/rest"

async def handle_bitrix_event(payload):
    event = payload.get("event")
    dialog_id = payload.get("data", {}).get("PARAMS", {}).get("DIALOG_ID")
    message = payload.get("data", {}).get("PARAMS", {}).get("MESSAGE")

    if event == "ONIMBOTMESSAGEADD":
        reply = await get_chatling_response(message)
        await send_message_to_bitrix(dialog_id, reply)
        return {"status": "ok"}
    return {"status": "ignored"}

async def send_message_to_bitrix(dialog_id, message):
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{BITRIX_WEBHOOK_URL}/imbot.message.add",
            data={
                "BOT_ID": get_bot_token(),
                "DIALOG_ID": dialog_id,
                "MESSAGE": message
            }
        )
