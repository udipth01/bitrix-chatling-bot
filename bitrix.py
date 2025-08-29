import httpx
from chatling import get_chatling_response

# ✅ Use your permanent webhook (no auth param needed)
BITRIX_WEBHOOK_URL = "https://finideas.bitrix24.in/rest/24/79r2m74ous5yme5r/"

async def handle_bitrix_event(payload):
    event = payload.get("event")
    dialog_id = payload.get("data", {}).get("PARAMS", {}).get("DIALOG_ID")
    message = payload.get("data", {}).get("PARAMS", {}).get("MESSAGE")

    if event == "ONIMBOTMESSAGEADD" and dialog_id and message:
        # Ask Chatling for a reply
        reply = await get_chatling_response(message, session_id=dialog_id)
        # Send reply back to Bitrix chat
        await send_message_to_bitrix(dialog_id, reply)
        return {"status": "ok"}

    return {"status": "ignored"}

async def send_message_to_bitrix(dialog_id, message):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{BITRIX_WEBHOOK_URL}im.message.add.json",
                json={
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
