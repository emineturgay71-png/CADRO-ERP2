#!/usr/bin/env python3
"""CADRO control-plane service — receives payment webhooks and enforces the grace period.

Run next to the bench (suspending or reactivating a site calls `bench`):

    CADRO_WEBHOOK_SECRET_FILE=/run/secrets/webhook_secret \
        python -m cadro.saas.control_plane serve --host 127.0.0.1 --port 8090

    python -m cadro.saas.control_plane sweep        # hourly, e.g. from cron

Endpoints:
    GET  /healthz            -> 200 {"status": "ok"}
    POST /webhooks/generic   -> CADRO signed JSON; headers X-Cadro-Timestamp and X-Cadro-Signature
                                (see cadro.saas.webhook.sign)

Answers: 200 {"outcome": ...} applied / duplicate / ignored / ...; 400 malformed or inconsistent;
401 bad or stale signature; 404 unknown tenant; 413 body too large; 500 apply failed (the provider
should retry; the event id is released so the retry is processed). The service never echoes the
secret, a signature or the body.

It speaks plain HTTP: put the TLS-terminating reverse proxy in front of it. The secret comes
from a file so that it never appears in a process list or an environment dump.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from cadro.saas import webhook

log = logging.getLogger("cadro.saas.control_plane")

MAX_BODY_BYTES = 64 * 1024


def load_secret() -> bytes:
    """Read the webhook shared secret from the file named by CADRO_WEBHOOK_SECRET_FILE."""
    path = os.environ.get("CADRO_WEBHOOK_SECRET_FILE")
    if not path:
        raise RuntimeError("CADRO_WEBHOOK_SECRET_FILE is not set")
    return Path(path).read_text(encoding="utf-8").strip().encode()


def make_handler(secret: bytes, actions: webhook.SiteActions | None = None):
    """Build the request handler class bound to a secret (and, in tests, to fake site actions)."""

    class Handler(BaseHTTPRequestHandler):
        server_version = "CadroControlPlane"
        sys_version = ""

        def _reply(self, status: int, body: dict) -> None:
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format, *args):  # noqa: A002 - signature fixed by the base class
            log.info("%s %s", self.address_string(), format % args)

        def do_GET(self):
            if self.path == "/healthz":
                self._reply(200, {"status": "ok"})
            else:
                self._reply(404, {"error": "not found"})

        def do_POST(self):
            if self.path != "/webhooks/generic":
                self._reply(404, {"error": "not found"})
                return

            try:
                length = int(self.headers.get("Content-Length", ""))
            except ValueError:
                self._reply(400, {"error": "Content-Length is required"})
                return
            if length < 0 or length > MAX_BODY_BYTES:
                self._reply(413, {"error": "body too large"})
                return
            raw = self.rfile.read(length)

            try:
                payload = webhook.normalize_generic(
                    raw,
                    self.headers.get("X-Cadro-Signature", ""),
                    self.headers.get("X-Cadro-Timestamp", ""),
                    secret,
                )
                outcome = webhook.handle_webhook(payload, actions)
            except webhook.InvalidSignature:
                self._reply(401, {"error": "invalid signature"})
            except LookupError:
                self._reply(404, {"error": "unknown tenant"})
            except ValueError as error:
                self._reply(400, {"error": str(error)})
            except Exception:
                log.exception("webhook processing failed")
                self._reply(500, {"error": "processing failed"})
            else:
                self._reply(200, {"outcome": outcome})

    return Handler


def serve(host: str, port: int) -> None:
    server = ThreadingHTTPServer((host, port), make_handler(load_secret()))
    log.info("control plane listening on %s:%s", host, port)
    try:
        server.serve_forever()
    finally:
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="CADRO control-plane service")
    sub = parser.add_subparsers(dest="command", required=True)
    serve_parser = sub.add_parser("serve", help="run the webhook receiver")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8090)
    sub.add_parser("sweep", help="suspend tenants whose trial or payment grace period ended")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    try:
        if args.command == "serve":
            serve(args.host, args.port)
        else:
            suspended = webhook.sweep_overdue()
            print(f"Suspended {len(suspended)} tenant(s): {', '.join(suspended) or '-'}")
    except (RuntimeError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
