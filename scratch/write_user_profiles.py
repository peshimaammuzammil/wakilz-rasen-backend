import httpx

FIREBASE_API_KEY = "AIzaSyAieaNn9LzmBQ8yulaqmW5K3mXkHseJ7g8"
FIREBASE_PROJECT_ID = "wakilz-dasboard"

def add_user_doc(email, password, uid, role="client", name="ClientDemo", client_id="wakilz_demo"):
    # Sign in to get fresh ID token
    signin_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
    resp = httpx.post(signin_url, json={"email": email, "password": password, "returnSecureToken": True})
    data = resp.json()
    id_token = data["idToken"]
    user_uid = data["localId"]
    print(f"Signed in as {email}, UID: {user_uid}")

    # Write document via Firestore REST API commit
    commit_url = f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}/databases/(default)/documents:commit"
    headers = {"Authorization": f"Bearer {id_token}"}

    body = {
        "writes": [
            {
                "update": {
                    "name": f"projects/{FIREBASE_PROJECT_ID}/databases/(default)/documents/users/{user_uid}",
                    "fields": {
                        "email": {"stringValue": email},
                        "role": {"stringValue": role},
                        "displayName": {"stringValue": name},
                        "clientId": {"stringValue": client_id},
                    }
                }
            }
        ]
    }

    res = httpx.post(commit_url, json=body, headers=headers)
    print(f"Commit write response {res.status_code}:", res.text)

# Add for client.demo@wakilz.com
add_user_doc("client.demo@wakilz.com", "DemoClient123!", "MWzf7sevUXeEz5yzzAD4LUg2mIu2", "client", "ClientDemo", "wakilz_demo")
# Add for admin.demo@wakilz.com
add_user_doc("admin.demo@wakilz.com", "AdminDemo123!", "PMM4D04232gQ2M0fZhj5qmx6EjW2", "admin", "AdminDemo", "wakilz_demo")
