import httpx

CHATLING_API_URL = "https://api.chatling.ai/v1/query"
CHATLING_BOT_ID = "4367189383"
CHATLING_API_KEY = "KfWnpNXL3LJ8f8872g898SP5J179DN6zyJUT488AxVW35QGl4LCS6prek7F1v3V3"

async def get_chatling_response(user_message: str, session_id: str = "default-session"):
    """
    Send message to Chatling and return AI reply.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                CHATLING_API_URL,
                headers={
                    "Authorization": f"Bearer {CHATLING_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "chatbot_id": CHATLING_BOT_ID,
                    "message": user_message,
                    "session_id": session_id
                }
            )
            response.raise_for_status()
            data = response.json()
            # 🔍 Adjusted parsing since Chatling wraps response
            reply = (
                data.get("reply")
                or data.get("answer")
                or data.get("data", {}).get("answer")
                or data.get("data", {}).get("reply")
            )
            return reply or "No reply from Chatling."
        except httpx.HTTPStatusError as e:
            return f"Chatling API error: {e.response.status_code} - {e.response.text}"
        except Exception as e:
            return f"Unexpected error: {str(e)}"
