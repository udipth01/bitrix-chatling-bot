# Chatling Bitrix Webhook

FastAPI server to handle Bitrix24 webhook events and respond via Chatling.

## Endpoints

- `POST /bitrix-handler`: Receives Bitrix webhook payloads and replies via bot.

## Setup

```bash
pip install -r requirements.txt
uvicorn main:app --reload