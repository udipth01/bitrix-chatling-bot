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
    Bitrix webhook entrypoint. Parses payload, 
    sends user message to Chatling, and posts reply back.
    """
    headers = dict(request.headers)
    logger.info("Received headers: %s", headers)

    body_bytes = await request.body()
    body_str = body_bytes.decode("utf-8", errors="replace")
    logger.info("Raw body: %s", body_str)

    # Parse form-encoded payload
    parsed = parse_qs(body_str)
    logger.info("Parsed form data: %s", parsed)

    # Extract fields
    event = parsed.get("event", [""])[0]
    message = parsed.get("data[PARAMS][MESSAGE]", [""])[0]
    dialog_id = parsed.get("data[PARAMS][DIALOG_ID]", [""])[0]

    logger.info(f"Event: {event}, Message: {message}, Dialog ID: {dialog_id}")

    if event == "ONIMBOTMESSAGEADD" and message:
        response = await handle_bitrix_event(event, dialog_id, message)
        return response

    return {"status": "ignored", "reason": "non-message event or empty message"}

@app.get("/")
def health():
    return {"status": "alive"}
