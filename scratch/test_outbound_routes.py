import httpx

BASE = "http://localhost:8080"

# 1. Verify key → token
r_auth = httpx.get(f"{BASE}/api/client/verify", params={"key": "wakilz_demo"}, timeout=5)
token = r_auth.json()["token"]
headers = {"Authorization": f"Bearer {token}"}
print("Auth verify:", r_auth.status_code)

# 2. GET /api/rasen/agents
r_agents = httpx.get(f"{BASE}/api/rasen/agents", headers=headers, timeout=10)
print("Agents:", r_agents.status_code, r_agents.json())

# 3. GET /api/rasen/phone-numbers
r_pns = httpx.get(f"{BASE}/api/rasen/phone-numbers", headers=headers, timeout=10)
print("Phone Numbers:", r_pns.status_code, r_pns.json())

# 4. GET /api/rasen/batch-calls
r_batches = httpx.get(f"{BASE}/api/rasen/batch-calls", headers=headers, timeout=10)
print("Batch Calls:", r_batches.status_code, r_batches.json())
