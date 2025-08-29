from fastapi import FastAPI, Request
from bitrix import handle_bitrix_event
from chatling import get_chatling_response

app = FastAPI()

@app.post("/bitrix-handler")
async def bitrix_webhook(request: Request):
    payload = await request.json()
    response = await handle_bitrix_event(payload)
    return response

@app.get("/")
def health():
    return {"status": "alive"}