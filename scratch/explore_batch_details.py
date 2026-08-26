import httpx
from server.core.config import RASEN_API_BASE, RASEN_API_KEY

headers = {
    "Authorization": f"Bearer {RASEN_API_KEY}",
    "Content-Type": "application/json",
}

batch_id = "4a579f84-fab1-445e-97d6-bdd31043a782"

# 1. GET /batch-calls/{id}
r = httpx.get(f"{RASEN_API_BASE}/batch-calls/{batch_id}", headers=headers)
print("GET /batch-calls/{id}:", r.status_code, r.text)

# 2. Check sub-endpoints like /calls, /recipients, /cancel, /stop
for ep in [f"/batch-calls/{batch_id}/calls", f"/batch-calls/{batch_id}/recipients", f"/batch-calls/{batch_id}/cancel", f"/batch-calls/{batch_id}/pause", f"/batch-calls/{batch_id}/stop"]:
    r_sub = httpx.get(f"{RASEN_API_BASE}{ep}", headers=headers)
    print(f"GET {ep}:", r_sub.status_code, r_sub.text[:150])
