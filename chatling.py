import httpx
import logging
import json
import os
from dotenv import load_dotenv
from supabase import create_client, Client
import re

load_dotenv()  

logger = logging.getLogger("chatling")
logging.basicConfig(level=logging.INFO)

# Chatling v2 API details
CHATLING_BOT_ID = os.environ.get("CHATLING_BOT_ID")
CHATLING_API_KEY = os.environ.get("CHATLING_API_KEY")
CHATLING_API_URL = f"https://api.chatling.ai/v2/chatbots/{CHATLING_BOT_ID}/ai/kb/chat"

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# 🔹 Finideas startup prompt
BOT_PROMPT = """You are a Finideas sales agent. Your primary goal is to guide the client toward taking the first step in their investment journey by completing their KYC and becoming a registered Finideas client.

Respond in a clear, natural, and human-like manner — avoid sounding robotic or overly salesy.

Keep answers short, to the point, and easy to understand.

Engage the client by ending your responses with a thoughtful, open-ended question that gently leads them closer to registration.

Stay consultative, not pushy — focus on building trust and showing how Finideas can add value.

Always keep the conversation flowing, ensuring the client feels heard and encouraged to take action.

This is the first question from the client: 

"""





if not SUPABASE_URL or not SUPABASE_KEY:
    logger.error("Supabase credentials not found. Please check your .env file.")
else:
    logger.info(f"Supabase URL loaded: {SUPABASE_URL}")
    logger.info(f"Supabase Key present: {bool(SUPABASE_KEY)}")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

async def get_chatling_response(
    user_message: str,
    user_id: str = None,
    bitrix_dialog_id: str = None,
    bitrix_user_info: dict = None,  # Pass Bitrix user info here
    ai_model_id: int = 24, #using model GPT 4.1 nano
    language_id: int = None,
    temperature: float = None,
    instructions: list[str] | None = None, 
):
    conversation_id = None
    chatling_contact_id = None


    # Fallback: Use Bitrix user info if message has no info
    if bitrix_user_info:
        user_name = bitrix_user_info.get("data[USER][NAME]", [None])[0]
        first_name = bitrix_user_info.get("data[USER][FIRST_NAME]", [None])[0]
        last_name = bitrix_user_info.get("data[USER][LAST_NAME]", [None])[0]
        email = bitrix_user_info.get("data[USER][EMAIL]", [None])[0]   # if provided by Bitrix
        phone = bitrix_user_info.get("data[USER][PHONE]", [None])[0]   # if provided by Bitrix


    try:
        # Fetch existing conversation & contact from Supabase
        result = supabase.table("chat_mapping").select("*").eq("bitrix_dialog_id", bitrix_dialog_id).execute()
        logger.info(f"Supabase select result: {result}")

        if result.data and len(result.data) > 0:
            conversation_id = result.data[0].get("chatling_conversation_id")
            chatling_contact_id = result.data[0].get("chatling_contact_id")

            # If contact ID missing, create contact
            if not chatling_contact_id:
                logger.info(f"⚡ Chatling contact missing for dialog {bitrix_dialog_id}. Creating new contact...")
                chatling_contact_id = await get_or_create_chatling_contact(
                    name=user_name,
                    first_name = first_name,
                    last_name = last_name,
                    phone=phone,
                    email=email,
                    bitrix_dialog_id=bitrix_dialog_id,
                    bitrix_user_info = bitrix_user_info
                )
            logger.info(f"Found existing conversation: {conversation_id}, contact: {chatling_contact_id}")
        else:
            # No conversation exists; create new one
            logger.info(f"No existing conversation for dialog {bitrix_dialog_id}. A new conversation will be created.")
            user_message = BOT_PROMPT + user_message
            logger.info(f"User message to be sent to bot:\n{user_message}")
            # Always create contact if missing
            chatling_contact_id = await get_or_create_chatling_contact(
                name=user_name,
                first_name = first_name,
                last_name = last_name,
                phone=phone,
                email=email,
                bitrix_dialog_id=bitrix_dialog_id,
                bitrix_user_info = bitrix_user_info
            )
    except Exception as e:
        logger.error(f"Error fetching from Supabase: {str(e)}")

    # # Determine message to send
    # if conversation_id is None:
    #     # First message in new conversation → prepend BOT_PROMPT
    #     full_message = BOT_PROMPT + "\n" + user_message
    # else:
    #     # Existing conversation → send as is
    #     full_message = user_message

        # Determine message to send
    if conversation_id is None:
        # First message in new conversation → prepend BOT_PROMPT
        revised_message = BOT_PROMPT + user_message
    else:
        revised_message = user_message
        instructions = instructions

    # Log individual variables
    logger.info(f"user_message: {revised_message}")
    logger.info(f"conversation_id: {conversation_id}")
    logger.info(f"chatling_contact_id: {chatling_contact_id}")
    logger.info(f"user_id: {user_id}")
    logger.info(f"ai_model_id: {ai_model_id}")
    logger.info(f"language_id: {language_id}")
    logger.info(f"temperature: {temperature}")
    logger.info(f"instructions: {instructions}")



    # Prepare payload for Chatling API
    payload = {
        "message": revised_message,
        "conversation_id": conversation_id if conversation_id else None,
        "contact_id": chatling_contact_id if chatling_contact_id else None,
        "user_id": str(user_id) if user_id else None,
        "ai_model_id": ai_model_id,
        "language_id": language_id,
        "temperature": temperature,
        "instructions": instructions if instructions else []  # always an array
    }

    
    # Remove keys with None values
    payload = {k: v for k, v in payload.items() if v is not None}

    headers = {
        "Authorization": f"Bearer {CHATLING_API_KEY}",
        "Content-Type": "application/json"
    }

    logger.info(f"➡️ Sending message to Chatling API\nURL: {CHATLING_API_URL}\nPayload: {json.dumps(payload, indent=2)}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(CHATLING_API_URL, headers=headers, json=payload)
            logger.info(f"⬅️ Chatling response [{response.status_code}]: {response.text}")
            response.raise_for_status()
            try:
                data = response.json()
            except Exception as e:
                logger.error(f"Failed to parse Chatling JSON response: {str(e)} | Response text: {response.text}")
                return f"Failed to parse Chatling response."
            

            # Save new conversation ID if Chatling created one
            new_conversation_id = data.get("data", {}).get("conversation_id")
            if new_conversation_id and not conversation_id:
                try:
                    insert_result = supabase.table("chat_mapping").upsert({
                        "bitrix_dialog_id": bitrix_dialog_id,
                        "chatling_conversation_id": new_conversation_id,
                        "chatling_contact_id": chatling_contact_id
                    }).execute()
                    logger.info(f"Supabase insert/upsert result: {insert_result}")
                except Exception as e:
                    logger.error(f"Error inserting into Supabase: {str(e)}")

            reply = data.get("data", {}).get("response", "No reply from Chatling.")
            return reply

        except httpx.HTTPStatusError as e:
            logger.error(f"Chatling API error: {e.response.status_code} - {e.response.text}")
            return f"Chatling API error: {e.response.status_code} - {e.response.text}"
        except Exception as e:
            logger.error(f"Unexpected error sending to Chatling: {str(e)}")
            return f"Unexpected error: {str(e)}"


# async def get_or_create_chatling_contact(name=None, phone=None, email=None, bitrix_dialog_id=None):
#     # Check Supabase first
#     existing = supabase.table("chat_mapping").select("chatling_contact_id").eq("bitrix_dialog_id", bitrix_dialog_id).execute()
#     chatling_contact_id = existing.data[0].get("chatling_contact_id")
#     if chatling_contact_id:
#         return chatling_contact_id
#     else:
#         contact_id = await create_chatling_contact(name=name, phone=phone, email=email)
#         if contact_id:
#             supabase.table("chat_mapping").update({"chatling_contact_id": contact_id}).eq("bitrix_dialog_id", bitrix_dialog_id).execute()
#         return contact_id

async def get_or_create_chatling_contact(name=None,first_name=None,last_name=None, phone=None, email=None, bitrix_dialog_id=None,bitrix_user_info=None):
    # Check Supabase first
    try:
        logger.info(f"🔹 get_or_create_chatling_contact called with bitrix_dialog_id={bitrix_dialog_id}, name={name}, phone={phone}, email={email}")
        existing = supabase.table("chat_mapping").select("chatling_contact_id").eq("bitrix_dialog_id", bitrix_dialog_id).execute()
        logger.info(f"Supabase check for existing contact returned: {existing.data}")
    except Exception as e:
        logger.error(f"Error fetching from Supabase: {str(e)}")
        existing = None

    chatling_contact_id = None
    if existing and existing.data and len(existing.data) > 0:
        chatling_contact_id = existing.data[0].get("chatling_contact_id")
        if chatling_contact_id:
            logger.info(f"✅ Existing Chatling contact found: {chatling_contact_id}")
            return chatling_contact_id
    

        # Create new contact
    logger.info(f"⚡ No existing contact found. Creating new Chatling contact...")
    contact_id = await create_chatling_contact(first_name=first_name,last_name = last_name or "", phone=phone or "", email=email or "")

    if contact_id:
        try:
            supabase.table("chat_mapping").upsert({
            "bitrix_dialog_id": bitrix_dialog_id,
            "chatling_contact_id": contact_id
            }).execute()

            logger.info(f"✅ Supabase updated with new Chatling contact: {contact_id}")
        except Exception as e:
            logger.error(f"Error updating Supabase with new contact: {str(e)}")

    return contact_id


    # Else create new contact in Chatling
    # contact_id = await create_chatling_contact(name=name, phone=phone, email=email)

async def create_chatling_contact(first_name=None,last_name=None, phone=None, email=None):
    """
    Create a new Chatling Contact and return the contact_id
    """
    url = f"https://api.chatling.ai/v2/chatbots/{CHATLING_BOT_ID}/contacts"
    headers = {
        "Authorization": f"Bearer {CHATLING_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "properties": {
            "first_name": first_name or "Unknown",
            "last_name": last_name,
            "email": email,
            "phone": phone,
            "company_name": "FinIdeas"
        }
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            logger.info(f"➡️ Sending Chatling contact create request")
            logger.info(f"URL: {url}")
            logger.info(f"Payload: {json.dumps(payload, indent=2)}")

            resp = await client.post(url, headers=headers, json=payload)
            logger.info(f"⬅️ Chatling contact create response [{resp.status_code}] {resp.text}")
            resp.raise_for_status()
            data = resp.json()
            contact_id = data.get("data", {}).get("id")
            logger.info(f"Created Chatling contact: {contact_id}")
            return contact_id
        except Exception as e:
            logger.error(f"Error creating Chatling contact: {e} | Response: {resp.text if 'resp' in locals() else 'no response'}")
            return None
        