"""Anonymous HTTP evidence transport. No browser, proxy, cookies or redirects."""
import asyncio
import hashlib
import ipaddress
import socket
import ssl
from urllib.parse import urlsplit


class PolicyStop(ValueError):
    pass


def target(url, *, display_resource=False, browser_navigation=False):
    if not isinstance(url, str) or len(url) > 2048 or any(ord(c) <= 32 or ord(c) >= 127 for c in url):
        raise PolicyStop("Use an ASCII HTTP(S) URL of at most 2048 characters")
    try:
        p = urlsplit(url)
        port = p.port if p.port is not None else (443 if p.scheme == "https" else 80)
    except ValueError as exc:
        raise PolicyStop("Malformed URL") from exc
    if p.scheme not in ("http", "https") or not p.hostname or p.username is not None or p.password is not None:
        raise PolicyStop("Only credential-free HTTP(S) URLs are supported")
    if (not display_resource and (p.query or "?" in url)) or (not browser_navigation and (p.fragment or "#" in url)) or "\\" in url or "%" in p.netloc:
        raise PolicyStop("Query strings, fragments and ambiguous authorities are unsupported; no URL is rewritten")
    host = p.hostname.lower()
    authority = f"[{host}]" if ":" in host else host
    default = 443 if p.scheme == "https" else 80
    origin = f"{p.scheme}://{authority}" + (f":{port}" if port != default else "")
    return p, origin, port


def authorize(url, origins, fixture_origin, *, display_resource=False, browser_navigation=False):
    p, origin, port = target(url, display_resource=display_resource, browser_navigation=browser_navigation)
    if origin == fixture_origin:
        if p.hostname not in ("127.0.0.1", "::1") or p.scheme != "http" or port == 80:
            raise PolicyStop("Fixture authorization requires a literal loopback origin and explicit non-default port")
    elif origin not in origins or p.scheme != "https" or port != 443:
        raise PolicyStop("Origin is not authorized for public HTTPS capture")
    return p, origin, port


def public_address(address):
    ip = ipaddress.ip_address(address)
    return ip.is_global and not (ip.is_multicast or ip.is_reserved or ip.is_unspecified or ip.is_loopback
                                or getattr(ip, "ipv4_mapped", None) or getattr(ip, "sixtofour", None)
                                or getattr(ip, "teredo", None))


async def fetch(url, origins, fixture_origin, max_bytes, timeout, *, resource=False, redirect_receipt=False, display_resource=False, on_body=None, read_data=False, font_resource=False):
    """Resolve once, validate every answer, connect to one numeric address with original TLS SNI."""
    p, origin, port = authorize(url, origins, fixture_origin, display_resource=display_resource)
    writer = None
    async with asyncio.timeout(timeout):
        if origin == fixture_origin:
            addresses = [(socket.AF_INET6 if ":" in p.hostname else socket.AF_INET, p.hostname)]
        else:
            answers = await asyncio.get_running_loop().getaddrinfo(p.hostname, port, type=socket.SOCK_STREAM)
            addresses = [(item[0], item[4][0]) for item in answers]
            if not addresses or any(not public_address(address) for _, address in addresses):
                raise PolicyStop("DNS includes a non-public address")
        family, address = addresses[0]
        sock = socket.socket(family, socket.SOCK_STREAM)
        sock.setblocking(False)
        try:
            await asyncio.get_running_loop().sock_connect(sock, (address, port))
            reader, writer = await asyncio.open_connection(
                sock=sock, ssl=ssl.create_default_context() if p.scheme == "https" else None,
                server_hostname=p.hostname if p.scheme == "https" else None, limit=16384,
            )
            authority = p.netloc
            request_path = (p.path or '/') + ('?' + p.query if p.query else '')
            request = f"GET {request_path} HTTP/1.1\r\nHost: {authority}\r\nUser-Agent: Evident-Evidence/0.1\r\nAccept: {'*/*' if resource else 'text/html,text/plain'}\r\nAccept-Encoding: identity\r\nConnection: close\r\n\r\n"
            writer.write(request.encode("ascii"))
            await writer.drain()
            header = await reader.readuntil(b"\r\n\r\n")
            if len(header) > 16384:
                raise ValueError("Response headers exceed limit")
            lines = header.decode("iso-8859-1").split("\r\n")
            parts = lines[0].split(" ", 2)
            if len(parts) < 2 or parts[0] not in ("HTTP/1.0", "HTTP/1.1"):
                raise ValueError("Unsupported HTTP response")
            status = int(parts[1])
            if not 100 <= status <= 599:
                raise ValueError("Invalid HTTP status")
            headers = {}
            for line in lines[1:]:
                if not line:
                    continue
                key, sep, value = line.partition(":")
                key = key.lower()
                if not sep or key in headers:
                    # Repeated security/framing headers are ambiguous; other duplicates are immaterial.
                    if not sep or key in ("content-length", "transfer-encoding", "content-type", "content-encoding"):
                        raise ValueError("Ambiguous response headers")
                    continue
                headers[key] = value.strip()
            if 300 <= status < 400:
                if redirect_receipt and status in (301, 302, 303, 307, 308):
                    return {"status": status, "location": headers.get("location", ""), "fetched_url": url, "peer": address}
                raise PolicyStop("Redirect not followed; authorize and request the destination separately")
            mime = headers.get("content-type", "").split(";", 1)[0].strip().lower()
            resource_types = {"text/html", "text/plain", "text/css", "text/javascript", "application/javascript",
                              "image/png", "image/jpeg", "image/webp", "image/gif", "image/svg+xml", "image/x-icon",
                              "font/woff", "font/woff2", "font/ttf", "font/otf", "application/font-woff",
                              "application/x-font-ttf", "application/x-woff", "application/vnd.ms-fontobject", "application/x-javascript"}
            if font_resource:
                resource_types.update({"application/octet-stream", "binary/octet-stream"})
            if read_data:
                resource_types.update({"application/json", "application/ld+json", "text/x-component", "application/xml", "text/xml"})
            if mime not in (resource_types if resource else ("text/html", "text/plain")):
                raise ValueError("Unsupported display-resource MIME: " + mime if resource else "Only text/html and text/plain responses are supported")
            if headers.get("content-encoding", "identity").lower() != "identity":
                raise ValueError("Compressed responses are unsupported")
            transfer = headers.get("transfer-encoding", "").lower()
            length = headers.get("content-length")
            if transfer and (transfer != "chunked" or length is not None):
                raise ValueError("Unsupported or ambiguous HTTP framing")
            body = bytearray()
            if transfer == "chunked":
                while True:
                    size = int((await reader.readuntil(b"\r\n")).split(b";", 1)[0].strip(), 16)
                    if size < 0 or len(body) + size > max_bytes:
                        raise ValueError("Response exceeds byte limit")
                    if size == 0:
                        break
                    while size:
                        chunk = await reader.read(min(8192, size))
                        if not chunk:
                            raise ValueError("Incomplete response body")
                        if on_body:
                            on_body(len(chunk))
                        body.extend(chunk)
                        size -= len(chunk)
                    if await reader.readexactly(2) != b"\r\n":
                        raise ValueError("Malformed chunk")
            else:
                expected = int(length) if length is not None else None
                if expected is not None and not 0 <= expected <= max_bytes:
                    raise ValueError("Response exceeds byte limit")
                while expected is None or len(body) < expected:
                    available = (expected - len(body)) if expected is not None else max_bytes - len(body)
                    if available <= 0:
                        raise ValueError("Response reaches byte limit without a declared length")
                    chunk = await reader.read(min(8192, available))
                    if not chunk:
                        break
                    if on_body:
                        on_body(len(chunk))
                    body.extend(chunk)
                    if len(body) > max_bytes:
                        raise ValueError("Response exceeds byte limit")
                if expected is not None and len(body) != expected:
                    raise ValueError("Incomplete response body")
            if font_resource and mime in ("application/octet-stream","binary/octet-stream") and not bytes(body).startswith((b"wOFF",b"wOF2",b"OTTO",b"\x00\x01\x00\x00")):
                raise ValueError("Binary font lacks a supported font signature")
            if resource:
                return {"status": status, "mime": mime, "body": bytes(body), "content_type": headers["content-type"],
                        "csp": headers.get("content-security-policy", ""), "cors":headers.get("access-control-allow-origin", ""), "bytes": len(body),
                        "sha256": hashlib.sha256(body).hexdigest(), "peer": address, "fetched_url": url}
            # Strict decoding prevents false negatives caused by silently dropped bytes.
            encoding = "utf-8"
            for param in headers.get("content-type", "").split(";")[1:]:
                key, _, value = param.strip().partition("=")
                if key.lower() == "charset":
                    encoding = value.strip('"').lower()
            if encoding not in ("utf-8", "utf8", "us-ascii", "iso-8859-1", "windows-1252"):
                raise ValueError("Unsupported text encoding")
            return {"status": status, "mime": mime, "text": body.decode(encoding), "bytes": len(body),
                    "sha256": hashlib.sha256(body).hexdigest(), "peer": address, "fetched_url": url}
        finally:
            if writer is not None:
                # open_connection owns the socket, including its TLS transport. Closing
                # the original descriptor races other concurrent resource connections.
                writer.close()
                try:
                    async with asyncio.timeout(1):
                        await writer.wait_closed()
                except (OSError, TimeoutError):
                    writer.transport.abort()
            else:
                sock.close()
