"""URL safety boundary. No shell, no unrestricted local-network requests."""
from __future__ import annotations

import ipaddress
import os
import socket
from urllib.parse import urlparse, urlunparse, urldefrag


class UnsafeURL(ValueError):
    pass


def private_network_allowed() -> bool:
    return os.getenv("ALLOW_PRIVATE_NETWORK", "false").lower() in {"1", "true", "yes"}


def validate_url(raw: str, *, resolve: bool = True) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise UnsafeURL("Please provide a website URL.")
    raw = raw.strip()
    if len(raw) > 2048:
        raise UnsafeURL("URL is too long (maximum 2048 characters).")
    try:
        parsed = urlparse(raw)
        port = parsed.port
    except ValueError as exc:
        raise UnsafeURL("The URL contains an invalid host or port.") from exc
    if parsed.scheme.lower() not in {"http", "https"}:
        raise UnsafeURL("Only http:// and https:// URLs are supported.")
    if not parsed.hostname or parsed.username or parsed.password:
        raise UnsafeURL("URL must contain a valid hostname and no embedded credentials.")
    if any(ord(c) < 32 for c in raw) or "\\" in raw:
        raise UnsafeURL("URL contains unsupported control characters.")
    if parsed.hostname.lower().endswith(".local") and not private_network_allowed():
        raise UnsafeURL("Local-network hosts are blocked for security.")
    if port and port not in {80, 443} and not private_network_allowed():
        raise UnsafeURL("Only standard HTTP(S) ports are permitted.")
    host = parsed.hostname.rstrip(".").lower()
    if not host or len(host) > 253:
        raise UnsafeURL("Invalid hostname.")
    try:
        ascii_host = host.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise UnsafeURL("Invalid international domain name.") from exc
    if resolve:
        try:
            infos = socket.getaddrinfo(ascii_host, port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise UnsafeURL("Could not resolve the website hostname.") from exc
        if not infos:
            raise UnsafeURL("No DNS records found for this website.")
        if not private_network_allowed():
            for info in infos:
                address = ipaddress.ip_address(info[4][0])
                if not address.is_global:
                    raise UnsafeURL("Private, loopback, reserved and internal IP addresses are blocked.")
    netloc = ascii_host if not port else f"{ascii_host}:{port}"
    if ":" in ascii_host:
        netloc = f"[{ascii_host}]" + (f":{port}" if port else "")
    clean = parsed._replace(scheme=parsed.scheme.lower(), netloc=netloc, fragment="", params="")
    return urlunparse(clean)


def same_site(candidate: str, original: str) -> bool:
    a, b = urlparse(candidate), urlparse(original)
    return a.hostname and a.hostname == b.hostname and a.scheme in {"http", "https"}


def normalize_url(raw: str) -> str:
    base = urldefrag(raw)[0]
    parsed = urlparse(base)
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    # Drop tracking queries for predictable bounded crawling, but retain other parameters.
    from urllib.parse import parse_qsl, urlencode
    items = [(k,v) for k,v in parse_qsl(parsed.query, keep_blank_values=True) if not k.lower().startswith(("utm_", "fbclid", "gclid"))]
    return urlunparse(parsed._replace(path=path, query=urlencode(items), fragment=""))
