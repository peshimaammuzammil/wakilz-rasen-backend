import httpx
from server.core.config import RASEN_API_BASE, RASEN_API_KEY, RASEN_AGENT_ID

headers = {
    "Authorization": f"Bearer {RASEN_API_KEY}",
    "Content-Type": "application/json",
}

# 1. Send invalid POST to /batch-calls to see the schema validation error response
r = httpx.post(f"{RASEN_API_BASE}/batch-calls", headers=headers, json={})
print("POST /batch-calls (empty):", r.status_code, r.text)

# 2. Also check /calls for outbound call creation
r_call = httpx.post(f"{RASEN_API_BASE}/calls", headers=headers, json={})
print("POST /calls (empty):", r_call.status_code, r_call.text)

# 3. Check /outbound or /phone-numbers / calls / test call endpoints
for ep in ["/calls/outbound", "/phone-numbers/0ec4c6f4-9939-41b1-9aa5-2ed9f811d92e/call", "/test-call"]:
    r_test = httpx.post(f"{RASEN_API_BASE}{ep}", headers=headers, json={})
    print(f"POST {ep}:", r_test.status_code, r_test.text[:200])
