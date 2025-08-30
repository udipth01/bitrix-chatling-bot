from fastapi import FastAPI, Request
from urllib.parse import parse_qs
import logging
from dotenv import load_dotenv
from bitrix import handle_bitrix_event
import sys

load_dotenv()

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

    logger.info(f"Event: {event}, Message: {message}, Dialog ID: {dialog_id}, User ID: {user_id}")

    # Handle only real messages
    if event == "ONIMBOTMESSAGEADD":
        if not message:
            logger.info(f"Ignoring ONIMBOTMESSAGEADD with empty message for dialog {dialog_id}")
            return {"status": "ignored", "reason": "empty message"}

        # Optional: filter for specific keywords
        if "hello chatbot" in message.lower():
            logger.info(f"Processing message for dialog {dialog_id}")
            try:
                response = await handle_bitrix_event(
                    event=event,
                    dialog_id=dialog_id,
                    message=message,
                    user_id=user_id
                )
                return response
            except Exception as e:
                logger.error(f"Error handling Bitrix event: {str(e)}")
                return {"status": "error", "reason": str(e)}
        else:
            logger.info(f"Message ignored due to keyword filter: {message}")
            return {"status": "ignored", "reason": "keyword not found"}

    # Ignore non-message events
    logger.info(f"Ignoring non-message event {event} for dialog {dialog_id}")
    return {"status": "ignored", "reason": "non-message event or empty message"}


@app.get("/")
def health():
    return {"status": "alive"}
