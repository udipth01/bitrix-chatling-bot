import httpx

CHATLING_API_URL = "https://api.chatling.ai/conversations"
CHATLING_BOT_ID = "4367189383"
CHATLING_API_KEY = "KfWnpNXL3LJ8f8872g898SP5J179DN6zyJUT488AxVW35QGl4LCS6prek7F1v3V3"

async def get_chatling_response(user_message):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            CHATLING_API_URL,
            headers={"Authorization": f"Bearer {CHATLING_API_KEY}"},
            json={"bot_id": CHATLING_BOT_ID, "message": user_message}
        )
        return response.json().get("reply", "Sorry, I couldn't fetch a response.")