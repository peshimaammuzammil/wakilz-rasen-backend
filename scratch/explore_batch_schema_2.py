import httpx
from server.core.config import RASEN_API_BASE, RASEN_API_KEY, RASEN_AGENT_ID

headers = {
    "Authorization": f"Bearer {RASEN_API_KEY}",
    "Content-Type": "application/json",
}

# Test POST /batch-calls with agent_id, name, and various recipient formats
r = httpx.post(f"{RASEN_API_BASE}/batch-calls", headers=headers, json={
    "agent_id": RASEN_AGENT_ID,
    "name": "Test Batch Validation",
    "recipients": [{}]
})
print("POST /batch-calls with empty recipient:", r.status_code, r.text)

# Also test single outbound call POST /calls schema
r2 = httpx.post(f"{RASEN_API_BASE}/calls", headers=headers, json={
    "agent_id": RASEN_AGENT_ID,
    "to": "+919876543210",
    "invalid_field_test": True
})
print("POST /calls:", r2.status_code, r2.text)
