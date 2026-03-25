# NetScaler NITRO API — Python Client & Examples

A Python client library and example scripts for automating **Citrix NetScaler / Citrix ADC** appliances via the **NITRO REST API**.

---

## Table of Contents

- [What is the NITRO API?](#what-is-the-nitro-api)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Authentication](#authentication)
  - [Header-based authentication](#1-header-based-authentication)
  - [Session-based authentication](#2-session-based-authentication)
- [API Basics](#api-basics)
  - [URL structure](#url-structure)
  - [HTTP methods → CRUD](#http-methods--crud)
  - [Response format](#response-format)
- [Using the Python Client](#using-the-python-client)
- [Examples](#examples)
  - [Load Balancing](#load-balancing)
  - [SSL Certificate Management](#ssl-certificate-management)
- [Repository Structure](#repository-structure)
- [References](#references)

---

## What is the NITRO API?

**NITRO** (Network Interface Through REST Operations) is the built-in REST API exposed by every Citrix NetScaler / Citrix ADC appliance.  
It allows you to fully automate the appliance — creating virtual servers, managing SSL certificates, monitoring statistics, and more — using plain HTTP(S) requests and JSON payloads.

Key facts:
- Endpoint: `https://<NSIP>/nitro/v1/`
- Two resource namespaces: `/config/` (read-write) and `/stat/` (read-only statistics)
- Standard HTTP verbs: `GET`, `POST`, `PUT`, `DELETE`
- Responses are JSON

---

## Prerequisites

- Python 3.8+
- Network access to the NetScaler management IP (`NSIP`)
- An account with sufficient privileges on the appliance (default: `nsroot`)

---

## Installation

```bash
pip install -r requirements.txt
```

---

## Authentication

### 1. Header-based authentication

The simplest approach — pass credentials with every request via `X-NITRO-USER` and `X-NITRO-PASS` HTTP headers.  
Works when MFA is **not** enabled.

```python
import requests

nsip = "https://adc.example.local"

headers = {
    "Content-Type": "application/json",
    "X-NITRO-USER": "nsroot",
    "X-NITRO-PASS": "nsroot",
}

response = requests.get(
    f"{nsip}/nitro/v1/config/lbvserver",
    headers=headers,
    verify=False,   # disable for self-signed certs in dev only
)
print(response.json())
```

### 2. Session-based authentication

Log in once with `POST /nitro/v1/config/login` to receive a `NITRO_AUTH_TOKEN` cookie, then reuse it for subsequent requests.

```python
import requests

nsip = "https://adc.example.local"
session = requests.Session()

# Log in
resp = session.post(
    f"{nsip}/nitro/v1/config/login",
    json={"login": {"username": "nsroot", "password": "nsroot"}},
    verify=False,
)
resp.raise_for_status()

# The session now carries the NITRO_AUTH_TOKEN cookie automatically
servers = session.get(f"{nsip}/nitro/v1/config/lbvserver", verify=False)
print(servers.json())

# Log out when done
session.post(f"{nsip}/nitro/v1/config/logout", json={"logout": {}}, verify=False)
```

---

## API Basics

### URL structure

| Namespace | URL pattern | Purpose |
|-----------|-------------|---------|
| Config    | `https://<NSIP>/nitro/v1/config/<resource>` | Create/read/update/delete |
| Statistics | `https://<NSIP>/nitro/v1/stat/<resource>` | Read-only counters |

Example resource types: `lbvserver`, `server`, `service`, `sslcertkey`, `sslvserver_sslcertkey_binding`

### HTTP methods → CRUD

| HTTP method | NITRO operation |
|-------------|----------------|
| `POST`      | Create a resource |
| `GET`       | Read one or all resources |
| `PUT`       | Update an existing resource |
| `DELETE`    | Delete a resource |
| `POST` (with `?action=<action>`) | Invoke a named action (e.g., `enable`, `disable`) |

### Response format

Every response body follows this envelope:

```json
{
    "errorcode": 0,
    "message": "Done",
    "severity": "NONE",
    "lbvserver": [ { ... } ]
}
```

`errorcode == 0` means success. Any other value indicates an error described in `message`.

---

## Using the Python Client

The `netscaler.client.NetScalerClient` class wraps the raw HTTP calls and handles authentication, error checking, and JSON serialisation for you.

```python
from netscaler.client import NetScalerClient

with NetScalerClient("https://adc.example.local", "nsroot", "nsroot", verify_ssl=False) as ns:
    # List all LB virtual servers
    vservers = ns.get("lbvserver")
    print(vservers)

    # Create a new server (real server / back-end node)
    ns.create("server", {"name": "web01", "ipaddress": "10.0.0.10"})

    # Create an LB virtual server
    ns.create("lbvserver", {
        "name": "vs_http_80",
        "servicetype": "HTTP",
        "ipv46": "192.168.1.100",
        "port": 80,
        "lbmethod": "ROUNDROBIN",
    })
```

---

## Examples

### Load Balancing

See [`examples/02_load_balancing.py`](examples/02_load_balancing.py) for a complete walkthrough:

1. Create back-end servers
2. Create services (server + port)
3. Create an LB virtual server
4. Bind services to the virtual server
5. Query live statistics

### SSL Certificate Management

See [`examples/03_ssl_certificates.py`](examples/03_ssl_certificates.py) for:

1. Add a certificate-key pair from files already on the appliance
2. Create an SSL-type LB virtual server
3. Bind the certificate to the virtual server

---

## Repository Structure

```
netscaler/           ← Python package (reusable client)
│   __init__.py
│   client.py        ← NetScalerClient class
examples/
│   01_authentication.py   ← Login / logout demo
│   02_load_balancing.py   ← Full LB setup
│   03_ssl_certificates.py ← SSL cert management
requirements.txt
README.md
```

---

## References

- [Citrix ADC NITRO API Reference](https://developer-docs.netscaler.com/en-us/adc-nitro-api/current-release.html)
- [Performing Basic NITRO Operations](https://developer-docs.netscaler.com/en-us/adc-nitro-api/current-release/performing-basic-netscaler-operations.html)
- [Configure SSL Offload via NITRO](https://developer-docs.netscaler.com/en-us/adc-nitro-api/current-release/usecases/configure-ssl-offload-acceleration.html)
