import httpx
import logging
import json

logger = logging.getLogger("chatling")
logging.basicConfig(level=logging.INFO)

# Chatling v2 API details
CHATLING_BOT_ID = "4367189383"
CHATLING_API_KEY = "KfWnpNXL3LJ8f8872g898SP5J179DN6zyJUT488AxVW35QGl4LCS6prek7F1v3V3"
CHATLING_API_URL = f"https://api.chatling.ai/v2/chatbots/{CHATLING_BOT_ID}/ai/kb/chat"


async def get_chatling_response(
    user_message: str,
    session_id: str = "default-session",
    user_id: str = None,
    ai_model_id: int = None,
    language_id: int = None,
    temperature: float = None
):
    """
    Send message to Chatling v2 API and return AI reply.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            payload = {
                "message": user_message,
                "conversation_id": session_id,  # mapping session_id to conversation_id
            }
            if user_id:
                payload["user_id"] = str(user_id)
            if ai_model_id:
                payload["ai_model_id"] = ai_model_id
            if language_id:
                payload["language_id"] = language_id
            if temperature is not None:
                payload["temperature"] = temperature

            headers = {
                "Authorization": f"Bearer {CHATLING_API_KEY}",
                "Content-Type": "application/json"
            }

            # Log exactly what we are sending
            logger.info("Sending request to Chatling API")
            logger.info(f"URL: {CHATLING_API_URL}")
            logger.info(f"Headers: {json.dumps(headers, indent=2)}")
            logger.info(f"Payload: {json.dumps(payload, indent=2)}")

            response = await client.post(CHATLING_API_URL, headers=headers, json=payload)

            # Log raw response
            logger.info(f"Response status: {response.status_code}")
            logger.info(f"Response body: {response.text}")

            response.raise_for_status()
            data = response.json()

            # Extract the reply (based on API structure)
            reply = (
                data.get("output_text")
                or data.get("reply")
                or data.get("message")
                or "No reply from Chatling."
            )
            return reply

        except httpx.HTTPStatusError as e:
            logger.error(f"Chatling API error: {e.response.status_code} - {e.response.text}")
            return f"Chatling API error: {e.response.status_code} - {e.response.text}"
        except Exception as e:
            logger.error(f"Unexpected error sending to Chatling: {str(e)}")
            return f"Unexpected error: {str(e)}"
