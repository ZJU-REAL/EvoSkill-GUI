#!/usr/bin/env python3
"""In-container HTTP proxy chain with bypass for emulator→host (10.0.2.x).

The Android emulator's apps (Chrome, Maps, Mattermost RN) speak the HTTP
proxy protocol when Settings.Global.http_proxy is set, but AOSP's bypass
list (`global_http_proxy_exclusion_list`) does not propagate reliably
into Chromium's net stack. Pointing the emulator at this script instead
of the user-supplied proxy lets us handle the bypass deterministically:

    emulator app
        ↓ HTTP CONNECT / plain GET
    proxy_chain.py  (this script, listens on 0.0.0.0:LOCAL_PORT)
        ├── target in 10.0.2.x / 127.* / localhost → direct TCP
        └── otherwise                              → forward to UPSTREAM_PROXY

The emulator reaches us via 10.0.2.2:LOCAL_PORT (its host loopback alias),
which we pre-seed into Settings.Global.http_proxy from start_emulator.sh.

Env vars:
    UPSTREAM_PROXY  the user-supplied external proxy URL
                    (http://host:port). Required.
    LOCAL_PORT      port we listen on inside the container.
                    Default: 38888.
"""

import asyncio
import os
import sys
from datetime import datetime
from urllib.parse import urlparse


def log(msg: str) -> None:
    print(f"{datetime.now().strftime('%H:%M:%S')} proxy_chain: {msg}", flush=True)


# Hosts that must NOT be sent to the upstream external proxy. Anything in
# 10.0.2.x is the emulator-to-host loopback, 127.* and ::1 are container
# loopback, "localhost" is the same. We keep the list small and explicit;
# it's enforced by string match on the host portion of the target.
def is_bypass(host: str) -> bool:
    h = host.lower()
    if h in ("localhost", "127.0.0.1", "::1"):
        return True
    if h.startswith("10.0.2."):
        return True
    if h.startswith("127."):
        return True
    return False


# When the request comes from the emulator with `10.0.2.2` as the host,
# the proxy_chain (running inside the container, not the emulator) cannot
# route to that address — `10.0.2.2` is the slirp gateway alias only
# meaningful from the guest. Rewrite to `127.0.0.1` so the direct-connect
# branch lands on the container's actual loopback (where Mattermost,
# Mastodon, the benchmark server etc. all live).
def rewrite_bypass_host(host: str) -> str:
    if host.lower().startswith("10.0.2."):
        return "127.0.0.1"
    return host


async def pipe(src, dst):
    try:
        while True:
            data = await src.read(65536)
            if not data:
                break
            dst.write(data)
            await dst.drain()
    except (ConnectionResetError, BrokenPipeError, asyncio.IncompleteReadError):
        pass
    finally:
        try:
            dst.close()
        except Exception:
            pass


async def handle(client_reader, client_writer, upstream_host, upstream_port):
    peer = client_writer.get_extra_info("peername")
    peer_str = f"{peer[0]}:{peer[1]}" if peer else "?"

    try:
        first = await client_reader.readline()
    except Exception:
        client_writer.close()
        return
    if not first:
        client_writer.close()
        return

    parts = first.decode("latin-1", errors="replace").rstrip("\r\n").split(" ")
    if len(parts) < 3:
        client_writer.close()
        return
    method, target = parts[0], parts[1]

    raw_headers = bytearray()
    while True:
        line = await client_reader.readline()
        raw_headers += line
        if line in (b"\r\n", b"\n", b""):
            break

    # Resolve "where do I really need to go" from the request.
    if method.upper() == "CONNECT":
        host, _, port = target.partition(":")
        port = int(port or "443")
    else:
        # Plain HTTP. target is an absolute URL like http://host[:port]/path.
        if not target.lower().startswith("http://"):
            client_writer.write(b"HTTP/1.1 400 Bad Request\r\n\r\n")
            await client_writer.drain()
            client_writer.close()
            return
        u = urlparse(target)
        host = u.hostname or ""
        port = u.port or 80

    bypass = is_bypass(host)
    log(f"{'DIRECT' if bypass else 'CHAIN '} {method} {host}:{port}  from={peer_str}")

    if bypass:
        # Direct: open TCP to the real destination ourselves.
        target_host = rewrite_bypass_host(host)
        try:
            up_r, up_w = await asyncio.open_connection(target_host, port)
        except Exception as e:
            log(f"  direct connect to {target_host}:{port} failed: {e}")
            client_writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
            await client_writer.drain()
            client_writer.close()
            return

        if method.upper() == "CONNECT":
            client_writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            await client_writer.drain()
        else:
            # Replay the original first line + headers, but with origin-form path.
            path = (urlparse(target).path or "/") + (
                "?" + urlparse(target).query if urlparse(target).query else ""
            )
            up_w.write(f"{method} {path} HTTP/1.1\r\n".encode("latin-1"))
            up_w.write(bytes(raw_headers))
            await up_w.drain()
    else:
        # Chain: open TCP to upstream proxy, replay request verbatim.
        try:
            up_r, up_w = await asyncio.open_connection(upstream_host, upstream_port)
        except Exception as e:
            log(f"  upstream proxy connect failed: {e}")
            client_writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
            await client_writer.drain()
            client_writer.close()
            return
        up_w.write(first)
        up_w.write(bytes(raw_headers))
        await up_w.drain()

    await asyncio.gather(pipe(client_reader, up_w), pipe(up_r, client_writer))


async def main_async():
    upstream_url = os.environ.get("UPSTREAM_PROXY", "")
    local_port = int(os.environ.get("LOCAL_PORT", "38888"))
    if not upstream_url:
        log("FATAL: UPSTREAM_PROXY env var is empty; nothing to chain to")
        sys.exit(1)
    parsed = urlparse(upstream_url)
    if not parsed.hostname or not parsed.port:
        log(f"FATAL: cannot parse UPSTREAM_PROXY={upstream_url!r}")
        sys.exit(1)
    upstream_host, upstream_port = parsed.hostname, parsed.port

    server = await asyncio.start_server(
        lambda r, w: handle(r, w, upstream_host, upstream_port),
        host="0.0.0.0",
        port=local_port,
    )
    addrs = ", ".join(str(s.getsockname()) for s in server.sockets)
    log(f"listening on {addrs}, upstream={upstream_host}:{upstream_port}")
    async with server:
        await server.serve_forever()


def main():
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        log("shutting down")


if __name__ == "__main__":
    main()
