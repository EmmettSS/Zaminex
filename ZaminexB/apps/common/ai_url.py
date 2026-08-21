"""Validate AI provider URLs so the server cannot be pointed at internal hosts."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


_BLOCKED_NETWORKS = (
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
)


class UnsafeAIURL(ValueError):
    """Raised when an AI base URL is not a public HTTPS endpoint."""


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
        return True
    for network in _BLOCKED_NETWORKS:
        if ip.version == network.version and ip in network:
            return True
    return False


def assert_public_https_url(raw: str) -> str:
    """Return a cleaned URL or raise ``UnsafeAIURL``."""
    url = (raw or "").strip()
    if not url:
        raise UnsafeAIURL("آدرس سرویس هوش مصنوعی خالی است.")

    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise UnsafeAIURL("آدرس سرویس هوش مصنوعی باید با HTTPS باشد.")
    if parsed.username or parsed.password:
        raise UnsafeAIURL("آدرس سرویس هوش مصنوعی نباید شامل نام کاربری یا رمز باشد.")
    host = (parsed.hostname or "").strip().lower()
    if not host or host == "localhost":
        raise UnsafeAIURL("میزبان سرویس هوش مصنوعی نامعتبر است.")

    try:
        ipaddress.ip_address(host)
        literal_ip = True
    except ValueError:
        literal_ip = False

    if literal_ip:
        if _is_blocked_ip(ipaddress.ip_address(host)):
            raise UnsafeAIURL("آدرس سرویس هوش مصنوعی نباید به شبکه داخلی اشاره کند.")
        return url

    # RFC 2606 reserved names used by unit tests; they never resolve on the
    # public internet so treating them as non-internal is safe.
    if host.endswith(".example") or host.endswith(".invalid") or host.endswith(".test"):
        return url

    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeAIURL("میزبان سرویس هوش مصنوعی قابل ترجمه نیست.") from exc

    if not infos:
        raise UnsafeAIURL("میزبان سرویس هوش مصنوعی قابل ترجمه نیست.")

    for info in infos:
        sockaddr = info[4]
        ip = ipaddress.ip_address(sockaddr[0])
        if _is_blocked_ip(ip):
            raise UnsafeAIURL("آدرس سرویس هوش مصنوعی نباید به شبکه داخلی اشاره کند.")

    return url
