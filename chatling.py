import httpx
import logging
import json
import os
from dotenv import load_dotenv

from supabase import create_client, Client

load_dotenv()  


logger = logging.getLogger("chatling")
logging.basicConfig(level=logging.INFO)

# Chatling v2 API details
CHATLING_BOT_ID = "4367189383"
CHATLING_API_KEY = "KfWnpNXL3LJ8f8872g898SP5J179DN6zyJUT488AxVW35QGl4LCS6prek7F1v3V3"
CHATLING_API_URL = f"https://api.chatling.ai/v2/chatbots/{CHATLING_BOT_ID}/ai/kb/chat"

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

async def create_chatling_conversation(user_id: str = None):
    async with httpx.AsyncClient(timeout=30.0) as client:
        payload = {}
        if user_id:
            payload["user_id"] = str(user_id)
        headers = {
            "Authorization": f"Bearer {CHATLING_API_KEY}",
            "Content-Type": "application/json"
        }
        response = await client.post(
            f"https://api.chatling.ai/v2/chatbots/{CHATLING_BOT_ID}/ai/kb/conversation",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        data = response.json()
        return data["conversation_id"]


async def get_chatling_response(
    user_message: str,
    session_id: str = "default-session",
    user_id: str = None,
    ai_model_id: int = 8,
    language_id: int = None,
    temperature: float = None,
    bitrix_dialog_id: str = None
):
    result = supabase.table("chat_mapping").select("*").eq("bitrix_dialog_id", bitrix_dialog_id).execute()
    data = result.data
    if data and len(data) > 0:
        conversation_id = data[0]["chatling_conversation_id"]
        logger.info(f"Found existing conversation: {conversation_id} for {bitrix_dialog_id}")
    else:
        conversation_id = await create_chatling_conversation(user_id=user_id)
        supabase.table("chat_mapping").insert({
            "bitrix_dialog_id": bitrix_dialog_id,
            "chatling_conversation_id": conversation_id
        }).execute()
        logger.info(f"No conversation found for {bitrix_dialog_id}, creating new one.")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            payload = {
                "message": user_message,
                "conversation_id": conversation_id,
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
