"""
Example 02 — Load Balancing
============================

Demonstrates a complete HTTP load-balancing setup using the NITRO API:

  1. Create two back-end servers (real servers)
  2. Create services (server + protocol + port)
  3. Create an LB virtual server
  4. Bind services to the virtual server
  5. Query live statistics for the virtual server
  6. Clean up (delete everything created above)

Usage
-----
Set the three environment variables below and run::

    python examples/02_load_balancing.py

Environment variables
---------------------
NSIP      - Appliance management IP or hostname, e.g. ``192.168.1.1``
NSUSER    - Username (default: nsroot)
NSPASS    - Password
"""

import os
import time

from netscaler.client import NetScalerClient, NitroError

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
NSIP = os.environ.get("NSIP", "192.168.1.1")
NSUSER = os.environ.get("NSUSER", "nsroot")
NSPASS = os.environ.get("NSPASS", "nsroot")
BASE_URL = f"https://{NSIP}"
VERIFY = False  # set True in production

# Resources we will create (names chosen to avoid clashing with existing config)
SERVERS = [
    {"name": "example-web01", "ipaddress": "10.100.0.11"},
    {"name": "example-web02", "ipaddress": "10.100.0.12"},
]
SERVICES = [
    {"name": "example-svc01", "servername": "example-web01", "servicetype": "HTTP", "port": 80},
    {"name": "example-svc02", "servername": "example-web02", "servicetype": "HTTP", "port": 80},
]
VSERVER_NAME = "example-vs-http"
VSERVER_IP = "203.0.113.10"  # TEST-NET — replace with your VIP
VSERVER_PORT = 80


def setup(ns: NetScalerClient) -> None:
    """Create servers, services, and LB virtual server."""

    print("\n--- Creating back-end servers ---")
    for srv in SERVERS:
        ns.create("server", srv)
        print(f"  Created server: {srv['name']} ({srv['ipaddress']})")

    print("\n--- Creating services ---")
    for svc in SERVICES:
        ns.create("service", svc)
        print(f"  Created service: {svc['name']}")

    print("\n--- Creating LB virtual server ---")
    ns.create("lbvserver", {
        "name": VSERVER_NAME,
        "servicetype": "HTTP",
        "ipv46": VSERVER_IP,
        "port": VSERVER_PORT,
        "lbmethod": "ROUNDROBIN",
        "persistencetype": "NONE",
    })
    print(f"  Created vserver: {VSERVER_NAME} ({VSERVER_IP}:{VSERVER_PORT})")

    print("\n--- Binding services to vserver ---")
    for svc in SERVICES:
        ns.create("lbvserver_service_binding", {
            "name": VSERVER_NAME,
            "servicename": svc["name"],
        })
        print(f"  Bound {svc['name']} → {VSERVER_NAME}")


def show_stats(ns: NetScalerClient) -> None:
    """Display live statistics for the LB virtual server."""
    print("\n--- LB virtual server statistics ---")
    stats = ns.stat("lbvserver", VSERVER_NAME)
    if isinstance(stats, list):
        stats = stats[0] if stats else {}
    interesting = ["name", "state", "curclntconnections", "totalrequests", "health"]
    for key in interesting:
        if key in stats:
            print(f"  {key}: {stats[key]}")


def teardown(ns: NetScalerClient) -> None:
    """Remove everything created by setup()."""
    print("\n--- Cleaning up ---")

    # Unbind services first, then delete vserver
    for svc in SERVICES:
        try:
            ns.delete(f"lbvserver_service_binding/{VSERVER_NAME}", svc["name"])
        except NitroError:
            pass  # binding may already be gone

    try:
        ns.delete("lbvserver", VSERVER_NAME)
        print(f"  Deleted vserver: {VSERVER_NAME}")
    except NitroError as exc:
        print(f"  Could not delete vserver: {exc}")

    for svc in SERVICES:
        try:
            ns.delete("service", svc["name"])
            print(f"  Deleted service: {svc['name']}")
        except NitroError as exc:
            print(f"  Could not delete service {svc['name']}: {exc}")

    for srv in SERVERS:
        try:
            ns.delete("server", srv["name"])
            print(f"  Deleted server: {srv['name']}")
        except NitroError as exc:
            print(f"  Could not delete server {srv['name']}: {exc}")


if __name__ == "__main__":
    with NetScalerClient(BASE_URL, NSUSER, NSPASS, verify_ssl=VERIFY) as ns:
        setup(ns)
        time.sleep(1)   # allow the services to transition to UP state before querying stats
        show_stats(ns)
        teardown(ns)

    print("\nDone.")
