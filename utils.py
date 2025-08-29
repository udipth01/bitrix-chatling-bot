import os

def get_bot_token():
    return os.getenv("BITRIX_BOT_ID", "77142")