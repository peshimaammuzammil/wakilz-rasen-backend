import httpx
import os
from server.core.config import RASEN_API_BASE, RASEN_API_KEY, RASEN_AGENT_ID

headers = {
    "Authorization": f"Bearer {RASEN_API_KEY}",
    "Content-Type": "application/json",
}

print(f"Rasen API Base: {RASEN_API_BASE}")

# 1. Check /agents
try:
    r = httpx.get(f"{RASEN_API_BASE}/agents", headers=headers)
    print("/agents status:", r.status_code)
    if r.status_code == 200:
        agents = r.json()
        print("Agents:", [(a.get("id"), a.get("name")) for a in (agents if isinstance(agents, list) else agents.get("items", []))])
except Exception as e:
    print("/agents err:", e)

# 2. Check /phone-numbers
try:
    r = httpx.get(f"{RASEN_API_BASE}/phone-numbers", headers=headers)
    print("/phone-numbers status:", r.status_code)
    if r.status_code == 200:
        pns = r.json()
        print("Phone numbers:", pns)
except Exception as e:
    print("/phone-numbers err:", e)

# 3. Check /outbound or /batch-calls or /batches
for ep in ["/batch-calls", "/batches", "/outbound", "/outbound-calls", "/calls/batch"]:
    try:
        r = httpx.get(f"{RASEN_API_BASE}{ep}", headers=headers)
        print(f"{ep} status:", r.status_code)
        if r.status_code in (200, 400, 422):
            print(f"{ep} resp:", r.text[:200])
    except Exception as e:
        print(f"{ep} err:", e)
