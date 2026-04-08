"""Real connectivity testers for resource connections.

Each tester returns a list of check dicts compatible with the
ConnectivityTestResult schema:
    {"name": str, "passed": bool, "message": str, "duration_ms": int}
"""
from __future__ import annotations

import asyncio
import socket
import ssl
import time
from typing import Any
from urllib.parse import urlparse

import httpx


# ── Helpers ──────────────────────────────────────────────────

def _ms(start: float) -> int:
    return max(1, int((time.monotonic() - start) * 1000))


def _parse_host_port(endpoint: str, default_port: int = 443) -> tuple[str, int]:
    """Extract (host, port) from an endpoint URL or host:port string."""
    if "://" in endpoint:
        parsed = urlparse(endpoint)
        host = parsed.hostname or ""
        port = parsed.port or default_port
    else:
        parts = endpoint.rsplit(":", 1)
        host = parts[0]
        port = int(parts[1]) if len(parts) == 2 and parts[1].isdigit() else default_port
    return host, port


# ── Individual check runners ─────────────────────────────────

async def _check_dns(host: str) -> dict[str, Any]:
    t = time.monotonic()
    try:
        loop = asyncio.get_running_loop()
        addrs = await loop.getaddrinfo(host, None, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM)
        if not addrs:
            return {"name": "dns_resolve", "passed": False, "message": f"DNS 解析无结果: {host}", "duration_ms": _ms(t)}
        ip = addrs[0][4][0]
        return {"name": "dns_resolve", "passed": True, "message": f"DNS 解析成功: {host} → {ip}", "duration_ms": _ms(t)}
    except socket.gaierror as exc:
        return {"name": "dns_resolve", "passed": False, "message": f"DNS 解析失败: {exc}", "duration_ms": _ms(t)}
    except Exception as exc:
        return {"name": "dns_resolve", "passed": False, "message": f"DNS 解析异常: {exc}", "duration_ms": _ms(t)}


async def _check_tcp(host: str, port: int, timeout: float = 10.0) -> dict[str, Any]:
    t = time.monotonic()
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        writer.close()
        await writer.wait_closed()
        return {"name": "tcp_connect", "passed": True, "message": f"TCP 连接成功: {host}:{port}", "duration_ms": _ms(t)}
    except asyncio.TimeoutError:
        return {"name": "tcp_connect", "passed": False, "message": f"TCP 连接超时 ({timeout}s): {host}:{port}", "duration_ms": _ms(t)}
    except OSError as exc:
        return {"name": "tcp_connect", "passed": False, "message": f"TCP 连接失败: {exc}", "duration_ms": _ms(t)}
    except Exception as exc:
        return {"name": "tcp_connect", "passed": False, "message": f"TCP 连接异常: {exc}", "duration_ms": _ms(t)}


async def _check_tls(host: str, port: int, timeout: float = 10.0) -> dict[str, Any]:
    """Attempt a TLS handshake (allow self-signed certs common in enterprise vCenter)."""
    t = time.monotonic()
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port, ssl=ctx), timeout=timeout
        )
        writer.close()
        await writer.wait_closed()
        return {"name": "tls_handshake", "passed": True, "message": f"TLS 握手成功 (允许自签名证书)", "duration_ms": _ms(t)}
    except asyncio.TimeoutError:
        return {"name": "tls_handshake", "passed": False, "message": f"TLS 握手超时 ({timeout}s)", "duration_ms": _ms(t)}
    except ssl.SSLError as exc:
        return {"name": "tls_handshake", "passed": False, "message": f"TLS 握手失败: {exc}", "duration_ms": _ms(t)}
    except Exception as exc:
        return {"name": "tls_handshake", "passed": False, "message": f"TLS 握手异常: {exc}", "duration_ms": _ms(t)}


# ── vCenter specific checks ─────────────────────────────────

def _vcenter_base_url(endpoint: str) -> str:
    """Derive the HTTPS base URL from a vCenter endpoint (strip /sdk path if present)."""
    parsed = urlparse(endpoint)
    scheme = parsed.scheme or "https"
    host = parsed.hostname or ""
    port = parsed.port
    port_str = f":{port}" if port and port != 443 else ""
    return f"{scheme}://{host}{port_str}"


async def _check_vcenter_api(base_url: str, timeout: float = 15.0) -> dict[str, Any]:
    """
    Probe the vCenter REST API root.
    vSphere 7+ exposes /api, vSphere 6.5-6.7 exposes /rest.
    We also try /ui/login to detect if vCenter web is reachable.
    """
    t = time.monotonic()
    async with httpx.AsyncClient(verify=False, timeout=timeout, follow_redirects=True) as client:
        # Try /api first (vSphere 7+)
        try:
            resp = await client.get(f"{base_url}/api")
            if resp.status_code < 500:
                return {
                    "name": "vcenter_rest_api",
                    "passed": True,
                    "message": f"vCenter REST API 可达 (/api) · HTTP {resp.status_code}",
                    "duration_ms": _ms(t),
                }
        except Exception:
            pass

        # Fallback: /rest (vSphere 6.5-6.7)
        try:
            resp = await client.get(f"{base_url}/rest")
            if resp.status_code < 500:
                return {
                    "name": "vcenter_rest_api",
                    "passed": True,
                    "message": f"vCenter REST API 可达 (/rest) · HTTP {resp.status_code}",
                    "duration_ms": _ms(t),
                }
        except Exception:
            pass

        # Fallback: /ui (vCenter web UI login page)
        try:
            resp = await client.get(f"{base_url}/ui")
            if resp.status_code < 500:
                return {
                    "name": "vcenter_rest_api",
                    "passed": True,
                    "message": f"vCenter Web UI 可达 (/ui) · HTTP {resp.status_code}",
                    "duration_ms": _ms(t),
                }
        except Exception:
            pass

    return {
        "name": "vcenter_rest_api",
        "passed": False,
        "message": f"vCenter REST API 不可达: {base_url}/api, /rest, /ui 均无响应",
        "duration_ms": _ms(t),
    }


async def _check_vcenter_auth(
    base_url: str,
    username: str,
    password: str,
    timeout: float = 15.0,
) -> dict[str, Any]:
    """
    Authenticate against the vCenter REST API using POST /api/session (vSphere 7+)
    or POST /rest/com/vmware/cis/session (vSphere 6.5-6.7).
    On success, immediately deletes the session to clean up.
    """
    t = time.monotonic()
    auth = httpx.BasicAuth(username, password)
    async with httpx.AsyncClient(verify=False, timeout=timeout, follow_redirects=True) as client:
        # vSphere 7+ session endpoint
        try:
            resp = await client.post(f"{base_url}/api/session", auth=auth)
            if resp.status_code in (200, 201):
                token = resp.text.strip().strip('"')
                try:
                    await client.delete(
                        f"{base_url}/api/session",
                        headers={"vmware-api-session-id": token},
                    )
                except Exception:
                    pass
                return {
                    "name": "vcenter_auth",
                    "passed": True,
                    "message": f"vCenter 认证成功 (vSphere 7+ API)",
                    "duration_ms": _ms(t),
                }
            elif resp.status_code == 401:
                return {
                    "name": "vcenter_auth",
                    "passed": False,
                    "message": f"vCenter 认证失败: 用户名或密码错误 (HTTP 401)",
                    "duration_ms": _ms(t),
                }
        except Exception:
            pass

        # vSphere 6.5-6.7 session endpoint
        try:
            resp = await client.post(f"{base_url}/rest/com/vmware/cis/session", auth=auth)
            if resp.status_code in (200, 201):
                try:
                    session_id = resp.json().get("value", "")
                    await client.delete(
                        f"{base_url}/rest/com/vmware/cis/session",
                        headers={"vmware-api-session-id": session_id},
                    )
                except Exception:
                    pass
                return {
                    "name": "vcenter_auth",
                    "passed": True,
                    "message": f"vCenter 认证成功 (vSphere 6.x REST)",
                    "duration_ms": _ms(t),
                }
            elif resp.status_code == 401:
                return {
                    "name": "vcenter_auth",
                    "passed": False,
                    "message": f"vCenter 认证失败: 用户名或密码错误 (HTTP 401)",
                    "duration_ms": _ms(t),
                }
        except Exception:
            pass

    return {
        "name": "vcenter_auth",
        "passed": False,
        "message": f"vCenter 认证端点不可达或请求异常",
        "duration_ms": _ms(t),
    }


# ── Orchestrator ─────────────────────────────────────────────

async def test_vcenter_connection(
    endpoint: str,
    username: str | None = None,
    password: str | None = None,
) -> list[dict[str, Any]]:
    """
    Run a full connectivity test suite against a vCenter endpoint.
    Steps: DNS → TCP → TLS → REST API → Auth (if credentials provided).
    Early-exit on critical failures (DNS/TCP).
    """
    host, port = _parse_host_port(endpoint, default_port=443)
    checks: list[dict[str, Any]] = []

    # 1. DNS
    dns = await _check_dns(host)
    checks.append(dns)
    if not dns["passed"]:
        return checks

    # 2. TCP
    tcp = await _check_tcp(host, port)
    checks.append(tcp)
    if not tcp["passed"]:
        return checks

    # 3. TLS
    tls = await _check_tls(host, port)
    checks.append(tls)

    # 4. vCenter REST API probe
    base_url = _vcenter_base_url(endpoint)
    api = await _check_vcenter_api(base_url)
    checks.append(api)

    # 5. Authentication (only if credentials supplied)
    if username and password:
        auth = await _check_vcenter_auth(base_url, username, password)
        checks.append(auth)
    else:
        checks.append({
            "name": "vcenter_auth",
            "passed": True,
            "message": "认证检查跳过（未提供凭据）",
            "duration_ms": 0,
        })

    return checks
