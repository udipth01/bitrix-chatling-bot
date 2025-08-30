from fastapi import FastAPI, Request
from urllib.parse import parse_qs
import logging

from bitrix import handle_bitrix_event

app = FastAPI()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bitrix-handler")

@app.post("/bitrix-handler")
async def bitrix_webhook(request: Request):
    """
    Bitrix webhook entrypoint. Parses payload, sends user message to Chatling,
    and posts reply back.
    """
    body_bytes = await request.body()
    body_str = body_bytes.decode("utf-8", errors="replace")
    parsed = parse_qs(body_str)

    event = parsed.get("event", [""])[0]
    message = parsed.get("data[PARAMS][MESSAGE]", [""])[0]
    dialog_id = parsed.get("data[PARAMS][DIALOG_ID]", [""])[0]
    user_id = parsed.get("data[PARAMS][FROM_USER_ID]", [""])[0]

    logger.info(f"Event: {event}, Message: {message}, Dialog ID: {dialog_id}")

    if event == "ONIMBOTMESSAGEADD" and message:
        # Only trigger Chatling if message contains "hello chatbot"
        if "hello chatbot" in message.lower():
            response = await handle_bitrix_event(event, dialog_id, message, user_id=user_id)
        else:
            response = {"status": "ignored", "reason": "keyword not found"}
        return response

    return {"status": "ignored", "reason": "non-message event or empty message"}

@app.get("/")
def health():
    return {"status": "alive"}
