"""
Script to create / configure Firebase Auth users and Firestore profiles for Wakilz.
Uses Firebase Identity Toolkit & Firestore REST APIs with the project Web API key.

Usage:
  python scripts/create_firebase_user.py --email admin@wakilz.com --password AdminPassword123! --role admin --name "Admin Wakilz"
  python scripts/create_firebase_user.py --email client@company.com --password ClientPassword123! --role client --name "Skyline Client" --client-id "wakilz_demo"
"""

import argparse
import json
import httpx

FIREBASE_API_KEY = "AIzaSyAieaNn9LzmBQ8yulaqmW5K3mXkHseJ7g8"
FIREBASE_PROJECT_ID = "wakilz-dasboard"

def create_user(email: str, password: str, role: str = "client", display_name: str = "", client_id: str = "wakilz_demo"):
    print(f"[*] Creating Firebase user for email: {email} with role: {role}...")
    
    # 1. Sign up / Create Auth user via Firebase Auth REST API
    signup_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_API_KEY}"
    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }
    
    resp = httpx.post(signup_url, json=payload, timeout=15.0)
    
    id_token = None
    uid = None
    
    if resp.status_code == 200:
        data = resp.json()
        uid = data.get("localId")
        id_token = data.get("idToken")
        print(f"[+] Successfully created Auth user! UID: {uid}")
    elif resp.status_code == 400 and "EMAIL_EXISTS" in resp.text:
        print(f"[!] User {email} already exists in Firebase Auth. Signing in to retrieve ID token...")
        signin_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
        signin_resp = httpx.post(signin_url, json=payload, timeout=15.0)
        if signin_resp.status_code == 200:
            data = signin_resp.json()
            uid = data.get("localId")
            id_token = data.get("idToken")
            print(f"[+] Retrieved token for existing user! UID: {uid}")
        else:
            print(f"[-] Sign in failed: {signin_resp.text}")
            return
    else:
        print(f"[-] Failed to create user in Firebase Auth: {resp.status_code} - {resp.text}")
        return

    # 2. Update display name if provided
    if display_name and id_token:
        update_url = f"https://identitytoolkit.googleapis.com/v1/accounts:update?key={FIREBASE_API_KEY}"
        httpx.post(update_url, json={"idToken": id_token, "displayName": display_name, "returnSecureToken": True}, timeout=10.0)

    # 3. Create or update Firestore profile document in `/users/{uid}` via Firestore REST API
    firestore_url = f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}/databases/(default)/documents/users/{uid}"
    headers = {"Authorization": f"Bearer {id_token}"}
    
    # Firestore REST expects typed fields
    firestore_fields = {
        "fields": {
            "email": {"stringValue": email},
            "role": {"stringValue": role},
            "displayName": {"stringValue": display_name or email.split("@")[0]},
            "clientId": {"stringValue": client_id},
        }
    }
    
    # Use PATCH to create or overwrite document
    patch_url = f"{firestore_url}?updateMask.fieldPaths=email&updateMask.fieldPaths=role&updateMask.fieldPaths=displayName&updateMask.fieldPaths=clientId"
    fs_resp = httpx.patch(patch_url, json=firestore_fields, headers=headers, timeout=15.0)
    
    if fs_resp.status_code == 200:
        print(f"[+] Successfully wrote profile to Firestore `/users/{uid}`:")
        print(f"    - Email: {email}")
        print(f"    - Role: {role}")
        print(f"    - Display Name: {display_name or email.split('@')[0]}")
        print(f"    - Client ID: {client_id}")
        print(f"\n[OK] User is ready to sign in at http://localhost:3000/signin !")
    else:
        print(f"[-] Failed to write Firestore document: {fs_resp.status_code} - {fs_resp.text}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create Firebase Auth user & Firestore profile")
    parser.add_argument("--email", required=True, help="User email address")
    parser.add_argument("--password", required=True, help="User password")
    parser.add_argument("--role", default="client", choices=["admin", "client"], help="User role (admin or client)")
    parser.add_argument("--name", default="", help="Display name")
    parser.add_argument("--client-id", default="wakilz_demo", help="Client ID for scoping data")
    
    args = parser.parse_args()
    create_user(args.email, args.password, args.role, args.name, args.client_id)
