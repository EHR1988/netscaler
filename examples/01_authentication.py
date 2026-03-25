"""
Example 01 — Authentication
============================

Demonstrates both ways to authenticate against the NITRO API:

  1. Header-based  (X-NITRO-USER / X-NITRO-PASS)
  2. Session-based (login → work → logout)  ← what NetScalerClient uses

Usage
-----
Set the three environment variables below and run::

    python examples/01_authentication.py

Environment variables
---------------------
NSIP      - Appliance management IP or hostname, e.g. ``192.168.1.1``
NSUSER    - Username (default: nsroot)
NSPASS    - Password
"""

import json
import os

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------------------------
# Configuration — read from environment to keep credentials out of source code
# ---------------------------------------------------------------------------
NSIP = os.environ.get("NSIP", "192.168.1.1")
NSUSER = os.environ.get("NSUSER", "nsroot")
NSPASS = os.environ.get("NSPASS", "nsroot")
BASE_URL = f"https://{NSIP}"
VERIFY = False  # set to True (or a CA bundle path) in production


# ---------------------------------------------------------------------------
# Method 1 — per-request header credentials (no session state)
# ---------------------------------------------------------------------------
def demo_header_auth() -> None:
    print("=== Method 1: Header-based authentication ===")

    headers = {
        "Content-Type": "application/json",
        "X-NITRO-USER": NSUSER,
        "X-NITRO-PASS": NSPASS,
    }

    response = requests.get(
        f"{BASE_URL}/nitro/v1/config/nsversion",
        headers=headers,
        verify=VERIFY,
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    print("nsversion:", json.dumps(data.get("nsversion", {}), indent=2))


# ---------------------------------------------------------------------------
# Method 2 — session-based (login / logout)
# ---------------------------------------------------------------------------
def demo_session_auth() -> None:
    print("\n=== Method 2: Session-based authentication ===")

    session = requests.Session()
    session.verify = VERIFY
    session.headers.update({"Content-Type": "application/json"})

    # Log in — the response sets a NITRO_AUTH_TOKEN cookie on the session
    login_resp = session.post(
        f"{BASE_URL}/nitro/v1/config/login",
        json={"login": {"username": NSUSER, "password": NSPASS}},
        timeout=10,
    )
    login_resp.raise_for_status()
    body = login_resp.json()
    if body.get("errorcode", 0) != 0:
        raise RuntimeError(f"Login failed: {body['message']}")

    print("Login successful. Session cookie:", dict(session.cookies))

    # Use the authenticated session
    version_resp = session.get(f"{BASE_URL}/nitro/v1/config/nsversion", timeout=10)
    version_resp.raise_for_status()
    data = version_resp.json()
    print("nsversion:", json.dumps(data.get("nsversion", {}), indent=2))

    # Always log out to release the server-side session slot
    session.post(
        f"{BASE_URL}/nitro/v1/config/logout",
        json={"logout": {}},
        timeout=10,
    )
    print("Logged out.")


# ---------------------------------------------------------------------------
# Method 3 — using the bundled NetScalerClient (recommended)
# ---------------------------------------------------------------------------
def demo_client_auth() -> None:
    print("\n=== Method 3: NetScalerClient context manager ===")

    from netscaler.client import NetScalerClient

    with NetScalerClient(BASE_URL, NSUSER, NSPASS, verify_ssl=VERIFY) as ns:
        versions = ns.get("nsversion")
        print("nsversion:", json.dumps(versions, indent=2))


if __name__ == "__main__":
    demo_header_auth()
    demo_session_auth()
    demo_client_auth()
