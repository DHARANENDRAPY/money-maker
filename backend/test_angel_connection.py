"""
Angel One SmartAPI Diagnostic & Connection Tester
Run with: python test_angel_connection.py
"""

import sys
import os
import time
import datetime
import email.utils
import base64
import hashlib
import hmac
import struct
import requests

# Ensure UTF-8 output handling on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    from dotenv import load_dotenv
    # Load from current directory or parent directory .env
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    pass

BASE_URL = "https://apiconnect.angelbroking.com"

ERROR_TRANSLATIONS = {
    "AG8001": "Invalid password or clientcode. Please verify that your Client Code is correct (uppercase, e.g. A123456) and your PIN is your 4 or 6 digit MPIN (not your old alphanumeric password).",
    "AG8002": "Invalid TOTP code. The 6-digit code generated from your TOTP secret was rejected by Angel One.",
    "AB1010": "Invalid TOTP. Ensure your TOTP Secret is the 16-32 character Base32 seed key (not the temporary 6-digit OTP) and that your system clock is accurate.",
    "AG8003": "Invalid Private Key (API Key). Ensure you copied the exact API Key created in your SmartAPI developer portal (https://smartapi.angelbroking.com/).",
    "AG8005": "TOTP is not enabled on your Angel One account. Please open the Angel One mobile app -> Profile -> Enable TOTP first.",
    "AB1004": "Client is blocked or inactive. Please check your Angel One account status.",
    "AB1000": "Internal server error at Angel One. Their API servers may be experiencing temporary downtime."
}

def clean_totp_secret(secret_str: str) -> str:
    return secret_str.strip().replace(" ", "").replace("-", "").upper()

def compute_totp(secret_str: str) -> str:
    clean_secret = clean_totp_secret(secret_str)
    if clean_secret.isdigit() and len(clean_secret) == 6:
        return clean_secret
    
    try:
        import pyotp
        return pyotp.TOTP(clean_secret).now()
    except Exception:
        pass
        
    try:
        padding = len(clean_secret) % 8
        if padding:
            clean_secret += "=" * (8 - padding)
        key = base64.b32decode(clean_secret)
        counter = int(time.time()) // 30
        msg = struct.pack(">Q", counter)
        h = hmac.new(key, msg, hashlib.sha1).digest()
        o = h[19] & 15
        token = (struct.unpack(">I", h[o:o+4])[0] & 0x7fffffff) % 1000000
        return f"{token:06d}"
    except Exception as e:
        return f"ERROR: {e}"

def mask_string(val: str, keep_visible: int = 3) -> str:
    if not val:
        return "[NOT SET]"
    if len(val) <= keep_visible:
        return "***"
    return val[:keep_visible] + "*" * (len(val) - keep_visible)

def run_diagnostics(api_key=None, client_code=None, pin=None, totp_secret=None):
    print("=" * 70)
    print("      ANGEL ONE SMARTAPI -- DEEP DIAGNOSTIC CONNECTION TEST      ")
    print("=" * 70)
    
    api_key = (api_key or os.getenv("ANGEL_API_KEY", "")).strip()
    client_code = (client_code or os.getenv("ANGEL_CLIENT_CODE", "")).strip().upper()
    pin = (pin or os.getenv("ANGEL_PIN", "")).strip()
    totp_secret = (totp_secret or os.getenv("ANGEL_TOTP_SECRET", "")).strip()
    
    print("\n[STEP 1] Checking Environment Credentials:")
    print(f"  * API Key      : {mask_string(api_key, 4)}")
    print(f"  * Client Code  : {mask_string(client_code, 3)}")
    print(f"  * Account PIN  : {'*' * len(pin) if pin else '[NOT SET]'}")
    print(f"  * TOTP Secret  : {mask_string(totp_secret, 4)} (Length: {len(clean_totp_secret(totp_secret))} chars)")
    
    missing = []
    if not api_key: missing.append("ANGEL_API_KEY")
    if not client_code: missing.append("ANGEL_CLIENT_CODE")
    if not pin: missing.append("ANGEL_PIN")
    if not totp_secret: missing.append("ANGEL_TOTP_SECRET")
    
    if missing:
        print(f"\n[!] INCOMPLETE: Missing required credentials in .env: {', '.join(missing)}")
        print("  Please edit your .env file with your credentials and re-run this test.")
        return False
        
    print("  [OK] All 4 credential fields are present.")

    # STEP 2: Network Connectivity & Server Clock Drift Check
    print("\n[STEP 2] Testing Network Connectivity & Time Synchronization:")
    try:
        start_t = time.time()
        resp = requests.get(f"{BASE_URL}/", timeout=6)
        latency_ms = int((time.time() - start_t) * 1000)
        print(f"  [OK] Angel One API Server is reachable! Ping latency: {latency_ms} ms (Status: {resp.status_code})")
        
        server_date_header = resp.headers.get("Date")
        if server_date_header:
            server_time_tuple = email.utils.parsedate_tz(server_date_header)
            if server_time_tuple:
                server_epoch = email.utils.mktime_tz(server_time_tuple)
                local_epoch = time.time()
                drift_seconds = abs(local_epoch - server_epoch)
                print(f"  * Angel One Server Time : {server_date_header}")
                print(f"  * Local Machine Time    : {datetime.datetime.now(datetime.timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT')}")
                print(f"  * Clock Drift Difference: {drift_seconds:.1f} seconds")
                
                if drift_seconds > 20:
                    print(f"  [WARN] Clock drift is {drift_seconds:.1f} seconds! TOTP codes may be rejected.")
                    print("     Fix: Sync your Windows clock in 'Date & Time Settings' -> 'Sync Now'.")
                else:
                    print("  [OK] Local system clock is synchronized within acceptable TOTP threshold.")
    except Exception as e:
        print(f"  [FAIL] Network Error: Could not connect to {BASE_URL}: {e}")
        return False

    # STEP 3: TOTP Code Generation & Verification
    print("\n[STEP 3] Validating TOTP Secret:")
    clean_secret = clean_totp_secret(totp_secret)
    if clean_secret.isdigit() and len(clean_secret) == 6:
        print("  [WARN] NOTICE: You entered a 6-digit number as your TOTP Secret.")
        print("     A temporary 6-digit OTP expires in 30 seconds!")
        print("     The TOTP Secret must be the permanent 16-32 character Base32 seed string (e.g. JBSWY3DPEHPK3PXP).")
    
    totp_code = compute_totp(totp_secret)
    if totp_code.startswith("ERROR"):
        print(f"  [FAIL] Failed to compute TOTP: {totp_code}")
        print("     The TOTP Secret is not valid Base32 format. Please re-copy the key from Angel One QR setup.")
        return False
        
    print(f"  [OK] TOTP algorithm generated current 6-digit code: [ {totp_code} ]")
    print("  >>> Check your phone's Google Authenticator app right now:")
    print(f"      Does the Angel One code on your phone match [ {totp_code} ]?")
    print("      If NO: Your TOTP Secret does NOT match the authenticator registered with this account.")

    # STEP 4: Login Authentication Attempt
    print("\n[STEP 4] Sending Authentication Request to Angel One:")
    url = f"{BASE_URL}/rest/auth/angelbroking/user/v1/loginByPassword"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-UserType": "USER",
        "X-SourceID": "WEB",
        "X-ClientLocalIP": "127.0.0.1",
        "X-ClientPublicIP": "127.0.0.1",
        "X-MACAddress": "02:00:00:00:00:00",
        "X-PrivateKey": api_key
    }
    payload = {
        "clientcode": client_code,
        "password": pin,
        "totp": totp_code
    }
    
    try:
        auth_resp = requests.post(url, headers=headers, json=payload, timeout=10)
        http_code = auth_resp.status_code
        print(f"  * HTTP Response Code: {http_code}")
        
        try:
            data = auth_resp.json()
        except Exception:
            print(f"  [FAIL] Response was not JSON. Raw body: {auth_resp.text[:300]}")
            return False
            
        status = data.get("status")
        message = data.get("message", "No message returned")
        error_code = data.get("errorcode", "")
        
        print(f"  * Status Flag        : {status}")
        print(f"  * Angel Message      : {message}")
        if error_code:
            print(f"  * Angel Error Code   : {error_code}")
            
        if status is True:
            token_data = data.get("data", {})
            jwt_token = token_data.get("jwtToken", "")
            feed_token = token_data.get("feedToken", "")
            print("\n" + "=" * 70)
            print("  SUCCESS! AUTHENTICATION COMPLETED SUCCESSFULLY!")
            print("=" * 70)
            print(f"  * JWT Token Received  : {mask_string(jwt_token, 10)}")
            print(f"  * Feed Token Received : {mask_string(feed_token, 6)}")
            
            # STEP 5: Test Quote Retrieval
            print("\n[STEP 5] Testing Live NSE Quote Retrieval (RELIANCE):")
            quote_url = f"{BASE_URL}/rest/secure/angelbroking/market/v1/quote/"
            quote_headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-UserType": "USER",
                "X-SourceID": "WEB",
                "X-ClientLocalIP": "127.0.0.1",
                "X-ClientPublicIP": "127.0.0.1",
                "X-MACAddress": "02:00:00:00:00:00",
                "X-PrivateKey": api_key,
                "Authorization": f"Bearer {jwt_token}"
            }
            quote_payload = {
                "mode": "LTP",
                "exchangeTokens": {
                    "NSE": ["2885"]  # RELIANCE token
                }
            }
            q_resp = requests.post(quote_url, headers=quote_headers, json=quote_payload, timeout=6)
            q_data = q_resp.json()
            if q_data.get("status") and q_data.get("data", {}).get("fetched"):
                fetched = q_data["data"]["fetched"][0]
                ltp = fetched.get("ltp")
                print(f"  [OK] Live NSE Quote Received! RELIANCE LTP: INR {ltp}")
                print("  [OK] Full Live Broker Streaming is 100% operational!")
            else:
                print(f"  [WARN] Quote response: {q_data.get('message', 'No items')}")
                
            return True
        else:
            print("\n" + "!" * 70)
            print("  AUTHENTICATION FAILED WITH ANGEL ONE")
            print("!" * 70)
            if error_code in ERROR_TRANSLATIONS:
                print(f"  EXPLANATION: {ERROR_TRANSLATIONS[error_code]}")
            else:
                print(f"  EXPLANATION: Angel One rejected the request. Message: '{message}' (Code: {error_code})")
                
            print("\n  Recommended Fixes:")
            print("  1. Verify your 4-6 digit MPIN is correct (do NOT use your website password).")
            print("  2. Verify your Client Code is capitalized (e.g. A123456).")
            print("  3. Verify your TOTP Secret matches the Base32 QR code key, not the 6-digit number.")
            print("  4. Check that your SmartAPI App status is 'Active' at https://smartapi.angelbroking.com/.")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"  [FAIL] Connection Timeout or Network Error: {e}")
        return False

if __name__ == "__main__":
    run_diagnostics()
