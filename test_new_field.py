import os
import requests

# Load from environment (or fallback hardcoded for quick test)
BITRIX_WEBHOOK_URL = "https://finideas.bitrix24.in/rest/24/79r2m7*****"
LEAD_ID = 558568   # replace with your test lead id
FIELD_NAME = "UF_CRM_1592568003637"

def get_lead_field(lead_id: int, field_name: str):
    url = f"{BITRIX_WEBHOOK_URL}/crm.lead.get.json"
    response = requests.post(url, json={"id": lead_id})
    response.raise_for_status()
    result = response.json()
    return result.get("result", {}).get(field_name)

def update_lead_field(lead_id: int, field_name: str, field_value) -> bool:
    url = f"{BITRIX_WEBHOOK_URL}/crm.lead.update.json"
    payload = {"id": lead_id, "fields": {field_name: field_value}}
    response = requests.post(url, json=payload)
    response.raise_for_status()
    result = response.json()
    return result.get("result", False)

if __name__ == "__main__":
    print("Before update →", get_lead_field(LEAD_ID, FIELD_NAME))

    # Toggle to True (1)
    success = update_lead_field(LEAD_ID, FIELD_NAME, 1)
    print("Update success:", success)

    print("After update →", get_lead_field(LEAD_ID, FIELD_NAME))
