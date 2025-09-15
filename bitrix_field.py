import requests

BITRIX_URL = "https://finideas.bitrix24.in/rest/24/79r****"  # replace

url = f"{BITRIX_URL}crm.lead.fields.json"
res = requests.get(url)
fields = res.json()

for code, info in fields["result"].items():
    print(code, "=>", info["title"])
