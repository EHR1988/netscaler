"""
netscaler.client
~~~~~~~~~~~~~~~~

Thin wrapper around the Citrix NetScaler / Citrix ADC NITRO REST API.

The NITRO API is a JSON-over-HTTP(S) interface built into every NetScaler
appliance.  All configuration lives under::

    https://<NSIP>/nitro/v1/config/<resource-type>

and read-only statistics are available at::

    https://<NSIP>/nitro/v1/stat/<resource-type>

This module exposes :class:`NetScalerClient`, a context-manager that handles
session authentication, error checking and JSON (de)serialisation so callers
can focus on business logic rather than HTTP plumbing.

Typical usage
-------------
::

    from netscaler.client import NetScalerClient

    with NetScalerClient("https://adc.example.local", "nsroot", "nsroot") as ns:
        vservers = ns.get("lbvserver")
        ns.create("server", {"name": "web01", "ipaddress": "10.0.0.10"})
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urljoin

import requests
import urllib3

logger = logging.getLogger(__name__)


class NitroError(Exception):
    """Raised when the NITRO API returns a non-zero error code."""

    def __init__(self, errorcode: int, message: str) -> None:
        self.errorcode = errorcode
        super().__init__(f"NITRO error {errorcode}: {message}")


class NetScalerClient:
    """Session-authenticated client for the Citrix NetScaler NITRO REST API.

    Parameters
    ----------
    host:
        Base URL of the appliance management interface, e.g.
        ``"https://192.168.1.1"`` or ``"https://adc.example.local"``.
    username:
        Appliance user name (default admin account is ``nsroot``).
    password:
        Corresponding password.
    verify_ssl:
        Whether to verify the appliance's TLS certificate.  Set to
        ``False`` when using self-signed certificates in a lab environment.
        **Always use** ``True`` **in production.**
    timeout:
        Default request timeout in seconds.

    Examples
    --------
    ::

        with NetScalerClient("https://adc.example.local", "nsroot", "nsroot") as ns:
            servers = ns.get("server")
            ns.create("server", {"name": "web01", "ipaddress": "10.0.0.10"})
    """

    _CONFIG_PATH = "/nitro/v1/config/"
    _STAT_PATH = "/nitro/v1/stat/"

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        *,
        verify_ssl: bool = True,
        timeout: int = 30,
    ) -> None:
        self._host = host.rstrip("/")
        self._username = username
        self._password = password
        self._verify_ssl = verify_ssl
        self._timeout = timeout
        self._session: requests.Session | None = None

        if not verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # ------------------------------------------------------------------
    # Context-manager protocol
    # ------------------------------------------------------------------

    def __enter__(self) -> "NetScalerClient":
        self.login()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        try:
            self.logout()
        except (NitroError, requests.RequestException):
            logger.warning("Logout failed — session may have already expired.")

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def login(self) -> None:
        """Create a new NITRO session.

        Sends ``POST /nitro/v1/config/login`` and stores the returned
        ``NITRO_AUTH_TOKEN`` cookie in the underlying :class:`requests.Session`.
        """
        self._session = requests.Session()
        self._session.verify = self._verify_ssl
        self._session.headers.update({"Content-Type": "application/json"})

        url = self._config_url("login")
        payload = {"login": {"username": self._username, "password": self._password}}

        resp = self._session.post(url, json=payload, timeout=self._timeout)
        self._raise_for_nitro_error(resp)
        logger.debug("Logged in to %s as %s", self._host, self._username)

    def logout(self) -> None:
        """Destroy the current NITRO session.

        Sends ``POST /nitro/v1/config/logout`` and closes the underlying
        :class:`requests.Session`.
        """
        if self._session is None:
            return
        try:
            url = self._config_url("logout")
            self._session.post(url, json={"logout": {}}, timeout=self._timeout)
            logger.debug("Logged out from %s", self._host)
        finally:
            self._session.close()
            self._session = None

    # ------------------------------------------------------------------
    # CRUD helpers (config namespace)
    # ------------------------------------------------------------------

    def get(self, resource: str, name: str | None = None, **params: Any) -> Any:
        """Read one or all resources of *resource* type.

        Parameters
        ----------
        resource:
            NITRO resource type, e.g. ``"lbvserver"``, ``"server"``.
        name:
            Optional resource name to retrieve a single object.
        **params:
            Extra query-string parameters forwarded to the API (e.g.
            ``attrs="name,ipv46"``).

        Returns
        -------
        list[dict] | dict
            The *resource* list returned by NITRO, or a single dict when
            *name* is supplied.
        """
        url = self._config_url(resource, name)
        resp = self._request("GET", url, params=params or None)
        return resp.get(resource, [])

    def create(self, resource: str, data: dict[str, Any]) -> dict[str, Any]:
        """Create a new *resource*.

        Parameters
        ----------
        resource:
            NITRO resource type, e.g. ``"lbvserver"``.
        data:
            Attribute dictionary for the new resource.  The wrapper key
            (``{resource: data}``) is added automatically.

        Returns
        -------
        dict
            The raw NITRO response envelope.
        """
        url = self._config_url(resource)
        return self._request("POST", url, json={resource: data})

    def update(self, resource: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update an existing *resource*.

        Parameters
        ----------
        resource:
            NITRO resource type.
        data:
            Attribute dictionary containing at minimum the resource's
            primary key (usually ``name``).

        Returns
        -------
        dict
            The raw NITRO response envelope.
        """
        url = self._config_url(resource)
        return self._request("PUT", url, json={resource: data})

    def delete(self, resource: str, name: str) -> dict[str, Any]:
        """Delete the *resource* identified by *name*.

        Parameters
        ----------
        resource:
            NITRO resource type.
        name:
            Name / primary key of the resource to delete.

        Returns
        -------
        dict
            The raw NITRO response envelope.
        """
        url = self._config_url(resource, name)
        return self._request("DELETE", url)

    def action(self, resource: str, action: str, data: dict[str, Any]) -> dict[str, Any]:
        """Invoke a named *action* on a *resource* (e.g. ``enable``, ``disable``).

        Parameters
        ----------
        resource:
            NITRO resource type.
        action:
            Action name, e.g. ``"enable"``, ``"disable"``, ``"rename"``.
        data:
            Attribute dictionary passed in the request body.

        Returns
        -------
        dict
            The raw NITRO response envelope.
        """
        url = self._config_url(resource)
        return self._request("POST", url, params={"action": action}, json={resource: data})

    # ------------------------------------------------------------------
    # Statistics namespace
    # ------------------------------------------------------------------

    def stat(self, resource: str, name: str | None = None) -> Any:
        """Return live statistics for *resource*.

        Parameters
        ----------
        resource:
            NITRO stat resource type, e.g. ``"lbvserver"``, ``"interface"``.
        name:
            Optional specific resource name.

        Returns
        -------
        list[dict] | dict
        """
        url = self._stat_url(resource, name)
        resp = self._request("GET", url)
        return resp.get(resource, [])

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _config_url(self, resource: str, name: str | None = None) -> str:
        path = f"{self._CONFIG_PATH}{resource}"
        if name is not None:
            path = f"{path}/{name}"
        return urljoin(self._host, path)

    def _stat_url(self, resource: str, name: str | None = None) -> str:
        path = f"{self._STAT_PATH}{resource}"
        if name is not None:
            path = f"{path}/{name}"
        return urljoin(self._host, path)

    def _request(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        if self._session is None:
            raise RuntimeError("Client is not logged in.  Use as a context manager or call login() first.")

        resp = self._session.request(method, url, timeout=self._timeout, **kwargs)
        return self._raise_for_nitro_error(resp)

    @staticmethod
    def _raise_for_nitro_error(resp: requests.Response) -> dict[str, Any]:
        """Parse the NITRO response and raise :class:`NitroError` on failure."""
        resp.raise_for_status()  # raise for HTTP-level errors (4xx, 5xx)
        body: dict[str, Any] = resp.json() if resp.content else {}
        errorcode = body.get("errorcode", 0)
        if errorcode != 0:
            raise NitroError(errorcode, body.get("message", "unknown error"))
        return body
