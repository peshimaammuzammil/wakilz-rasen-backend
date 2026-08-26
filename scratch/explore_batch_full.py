import httpx
from server.core.config import RASEN_API_BASE, RASEN_API_KEY, RASEN_AGENT_ID

headers = {
    "Authorization": f"Bearer {RASEN_API_KEY}",
    "Content-Type": "application/json",
}

# Let's test with full parameters to see if extra fields are accepted or validated
payload = {
    "agent_id": RASEN_AGENT_ID,
    "name": "Test Validation Probe",
    "from_number_id": "0ec4c6f4-9939-41b1-9aa5-2ed9f811d92e",
    "phone_number_id": "0ec4c6f4-9939-41b1-9aa5-2ed9f811d92e",
    "ringing_timeout": 60,
    "concurrency_limit": 5,
    "scheduled_at": None,
    "recipients": [
        {
            "phone_number": "+919999999999",
            "variables": {"name": "Test User", "city": "Delhi"},
            "first_message": "Hello Test",
            "system_prompt": "You are a helpful assistant",
            "language": "en",
            "voice_id": "alloy"
        }
    ]
}

r = httpx.post(f"{RASEN_API_BASE}/batch-calls", headers=headers, json=payload)
print("POST /batch-calls result:", r.status_code, r.text)

# Also check GET /batch-calls/{id} endpoint structure
r_list = httpx.get(f"{RASEN_API_BASE}/batch-calls", headers=headers)
print("GET /batch-calls list:", r_list.status_code, r_list.text)
