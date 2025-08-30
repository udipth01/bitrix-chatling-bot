import httpx
import logging

logger = logging.getLogger("chatling")



# Chatling v2 API details
CHATLING_API_URL = "https://api.chatling.ai/v2/query"
CHATLING_BOT_ID = "4367189383"
CHATLING_API_KEY = "KfWnpNXL3LJ8f8872g898SP5J179DN6zyJUT488AxVW35QGl4LCS6prek7F1v3V3"

async def get_chatling_response(user_message: str, session_id: str = "default-session", user_id: str = None):
    """
    Send message to Chatling v2 API and return AI reply.
    """
    logger.info(f"Sending to Chatling: message='{user_message}', session_id='{session_id}', user_id='{user_id}'")
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            payload = {
                "bot_id": CHATLING_BOT_ID,
                "input": user_message,
                "session_id": session_id
            }
            if user_id:
                payload["user_id"] = str(user_id)

            response = await client.post(
                CHATLING_API_URL,
                headers={
                    "Authorization": f"Bearer {CHATLING_API_KEY}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            logger.info(f"Sent to Bitrix response: {data}")
            # Extract the reply from the v2 structure
            reply = data.get("output_text") or data.get("reply") or "No reply from Chatling."
            return reply
        except httpx.HTTPStatusError as e:
            logger.error(f"Chatling API error: {e.response.status_code} - {e.response.text}")
            return f"Chatling API error: {e.response.status_code} - {e.response.text}"
        except Exception as e:
            logger.error(f"Unexpected error sending to Chatling: {str(e)}")
            return f"Unexpected error: {str(e)}"
