"""
Example 03 — SSL Certificate Management
=========================================

Demonstrates SSL certificate operations via the NITRO API:

  1. Add a certificate-key pair (cert and key files must already exist on
     the appliance under ``/nsconfig/ssl/``)
  2. Create an SSL-type LB virtual server
  3. Bind the certificate-key pair to the virtual server
  4. Verify the binding
  5. Clean up (delete everything created above)

Prerequisites
-------------
Before running this script, transfer your certificate and private-key files
to the appliance.  Using SCP::

    scp server.crt nsroot@<NSIP>:/nsconfig/ssl/
    scp server.key nsroot@<NSIP>:/nsconfig/ssl/

Usage
-----
Set the environment variables below and run::

    python examples/03_ssl_certificates.py

Environment variables
---------------------
NSIP      - Appliance management IP or hostname, e.g. ``192.168.1.1``
NSUSER    - Username (default: nsroot)
NSPASS    - Password
"""

import os

from netscaler.client import NetScalerClient, NitroError

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
NSIP = os.environ.get("NSIP", "192.168.1.1")
NSUSER = os.environ.get("NSUSER", "nsroot")
NSPASS = os.environ.get("NSPASS", "nsroot")
BASE_URL = f"https://{NSIP}"
VERIFY = False  # set True in production

# Paths on the *appliance* filesystem
CERT_FILE = "/nsconfig/ssl/example.crt"
KEY_FILE = "/nsconfig/ssl/example.key"

# Resource names
CERTKEY_NAME = "example-certkey"
VSERVER_NAME = "example-vs-ssl"
VSERVER_IP = "203.0.113.20"  # TEST-NET — replace with your VIP
VSERVER_PORT = 443


def add_certkey(ns: NetScalerClient) -> None:
    """Create a certificate-key pair object on the appliance."""
    print("\n--- Adding certificate-key pair ---")
    ns.create("sslcertkey", {
        "certkey": CERTKEY_NAME,
        "cert": CERT_FILE,
        "key": KEY_FILE,
        "inform": "PEM",
        "expirymonitor": "ENABLED",
        "notificationperiod": 30,
    })
    print(f"  Created certkey: {CERTKEY_NAME}")


def create_ssl_vserver(ns: NetScalerClient) -> None:
    """Create an SSL-type LB virtual server."""
    print("\n--- Creating SSL LB virtual server ---")
    ns.create("lbvserver", {
        "name": VSERVER_NAME,
        "servicetype": "SSL",
        "ipv46": VSERVER_IP,
        "port": VSERVER_PORT,
        "lbmethod": "LEASTCONNECTION",
        "persistencetype": "NONE",
    })
    print(f"  Created vserver: {VSERVER_NAME} ({VSERVER_IP}:{VSERVER_PORT})")


def bind_cert_to_vserver(ns: NetScalerClient) -> None:
    """Bind the certificate-key pair to the SSL virtual server."""
    print("\n--- Binding certificate to vserver ---")
    ns.create("sslvserver_sslcertkey_binding", {
        "vservername": VSERVER_NAME,
        "certkeyname": CERTKEY_NAME,
    })
    print(f"  Bound {CERTKEY_NAME} → {VSERVER_NAME}")


def verify_binding(ns: NetScalerClient) -> None:
    """List certificate bindings for the virtual server."""
    print("\n--- Certificate bindings on vserver ---")
    bindings = ns.get("sslvserver_sslcertkey_binding", VSERVER_NAME)
    if not bindings:
        print("  (no bindings found)")
        return
    for b in (bindings if isinstance(bindings, list) else [bindings]):
        print(f"  certkey: {b.get('certkeyname')}  CA: {b.get('ca', False)}")


def list_all_certkeys(ns: NetScalerClient) -> None:
    """List all certificate-key pairs on the appliance with their expiry info."""
    print("\n--- All certificate-key pairs on appliance ---")
    certkeys = ns.get("sslcertkey")
    for ck in (certkeys if isinstance(certkeys, list) else []):
        print(
            f"  {ck.get('certkey', '?'):40s}  "
            f"daystoexpiration={ck.get('daystoexpiration', '?')}"
        )


def teardown(ns: NetScalerClient) -> None:
    """Remove all resources created by this script."""
    print("\n--- Cleaning up ---")

    # Unbind cert from vserver
    try:
        ns.delete(f"sslvserver_sslcertkey_binding/{VSERVER_NAME}", CERTKEY_NAME)
        print("  Removed cert binding")
    except NitroError:
        pass

    try:
        ns.delete("lbvserver", VSERVER_NAME)
        print(f"  Deleted vserver: {VSERVER_NAME}")
    except NitroError as exc:
        print(f"  Could not delete vserver: {exc}")

    try:
        ns.delete("sslcertkey", CERTKEY_NAME)
        print(f"  Deleted certkey: {CERTKEY_NAME}")
    except NitroError as exc:
        print(f"  Could not delete certkey: {exc}")


if __name__ == "__main__":
    with NetScalerClient(BASE_URL, NSUSER, NSPASS, verify_ssl=VERIFY) as ns:
        add_certkey(ns)
        create_ssl_vserver(ns)
        bind_cert_to_vserver(ns)
        verify_binding(ns)
        list_all_certkeys(ns)
        teardown(ns)

    print("\nDone.")
