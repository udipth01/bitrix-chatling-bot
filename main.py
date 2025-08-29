from fastapi import FastAPI, Request
import json
import logging

from bitrix import handle_bitrix_event
from chatling import get_chatling_response

app = FastAPI()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bitrix-handler")

@app.post("/bitrix-handler")
async def bitrix_webhook(request: Request):
    # Log headers
    headers = dict(request.headers)
    logger.info("Received headers: %s", headers)

    # Log raw body
    body_bytes = await request.body()
    body_str = body_bytes.decode("utf-8", errors="replace")
    logger.info("Raw body: %s", body_str)

    # Try parsing JSON
    try:
        payload = json.loads(body_str)
        logger.info("Parsed JSON payload: %s", json.dumps(payload, indent=2))
    except json.JSONDecodeError as e:
        logger.error("JSON decode error: %s", str(e))
        return {"error": "Invalid JSON", "details": str(e)}

    # Proceed with your event handler
    response = await handle_bitrix_event(payload)
    return response

@app.get("/")
def health():
    return {"status": "alive"}