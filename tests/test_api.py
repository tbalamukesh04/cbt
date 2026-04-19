import httpx
import json

url = "http://127.0.0.1:8001/upload"
files = {'file': ('test_jee.pdf', open('test_jee.pdf', 'rb'), 'application/pdf')}

response = httpx.post(url, files=files)
data = response.json()

print(json.dumps(data, indent=2))
