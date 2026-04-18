from __future__ import annotations

import argparse
import json
from http.client import HTTPConnection, HTTPSConnection, HTTPResponse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit


HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Relay /v1 requests to an upstream server and normalize message content."
    )
    parser.add_argument("--listen-host", default="0.0.0.0", help="Relay server bind host")
    parser.add_argument("--listen-port", type=int, default=3100, help="Relay server bind port")
    parser.add_argument("--upstream-host", required=True, help="Upstream server host or IP")
    parser.add_argument("--upstream-port", type=int, required=True, help="Upstream server port")
    parser.add_argument(
        "--upstream-scheme",
        choices=("http", "https"),
        default="http",
        help="Upstream server scheme",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="Upstream request timeout in seconds",
    )
    return parser.parse_args()


def normalize_messages(payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    messages = payload.get("messages")
    if not isinstance(messages, list):
        return payload, False

    changed = False
    normalized_messages: list[Any] = []

    for message in messages:
        if not isinstance(message, dict):
            normalized_messages.append(message)
            continue

        content = message.get("content")
        if isinstance(content, list):
            text_parts: list[str] = []
            can_flatten = True
            for item in content:
                if not isinstance(item, dict) or item.get("type") != "text":
                    can_flatten = False
                    break
                text_value = item.get("text")
                if not isinstance(text_value, str):
                    can_flatten = False
                    break
                text_parts.append(text_value)

            if can_flatten:
                updated_message = dict(message)
                updated_message["content"] = "".join(text_parts)
                normalized_messages.append(updated_message)
                changed = True
                continue

        normalized_messages.append(message)

    if not changed:
        return payload, False

    updated_payload = dict(payload)
    updated_payload["messages"] = normalized_messages
    return updated_payload, True


def maybe_transform_body(path: str, body: bytes) -> tuple[bytes, bool]:
    if not path.startswith("/v1"):
        return body, False
    if not body:
        return body, False

    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return body, False

    if not isinstance(payload, dict):
        return body, False

    updated_payload, changed = normalize_messages(payload)
    if not changed:
        return body, False

    transformed_body = json.dumps(updated_payload, ensure_ascii=False).encode("utf-8")
    return transformed_body, True


class RelayServerHandler(BaseHTTPRequestHandler):
    server_version = "RelayServer/1.0"

    upstream_host: str
    upstream_port: int
    upstream_scheme: str
    upstream_timeout: float

    def _read_request_body(self) -> bytes:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            return b""
        return self.rfile.read(content_length)

    def _build_upstream_headers(self, body: bytes) -> dict[str, str]:
        headers: dict[str, str] = {}
        for key, value in self.headers.items():
            if key.lower() in HOP_BY_HOP_HEADERS:
                continue
            if key.lower() == "host":
                continue
            headers[key] = value

        headers["Host"] = f"{self.upstream_host}:{self.upstream_port}"
        headers["Content-Length"] = str(len(body))
        return headers

    def _open_connection(self) -> HTTPConnection | HTTPSConnection:
        connection_class = HTTPSConnection if self.upstream_scheme == "https" else HTTPConnection
        return connection_class(
            host=self.upstream_host,
            port=self.upstream_port,
            timeout=self.upstream_timeout,
        )

    def _relay(self) -> None:
        original_body = self._read_request_body()
        request_body, transformed = maybe_transform_body(self.path, original_body)
        headers = self._build_upstream_headers(request_body)

        print(f"{self.command} {self.path} -> {self.upstream_scheme}://{self.upstream_host}:{self.upstream_port}")
        if transformed:
            print("Request body transformed before forwarding.")

        connection = self._open_connection()
        try:
            connection.request(
                method=self.command,
                url=self.path,
                body=request_body,
                headers=headers,
            )
            upstream_response = connection.getresponse()
            self._write_upstream_response(upstream_response)
        except Exception as exc:
            error_body = json.dumps(
                {"error": "bad_gateway", "message": str(exc)},
                ensure_ascii=False,
            ).encode("utf-8")
            self.send_response(502)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(error_body)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(error_body)
        finally:
            connection.close()

    def _write_upstream_response(self, upstream_response: HTTPResponse) -> None:
        body = upstream_response.read()
        self.send_response(upstream_response.status, upstream_response.reason)

        for key, value in upstream_response.getheaders():
            if key.lower() in HOP_BY_HOP_HEADERS:
                continue
            if key.lower() == "content-length":
                continue
            self.send_header(key, value)

        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_GET(self) -> None:
        self._relay()

    def do_POST(self) -> None:
        self._relay()

    def do_PUT(self) -> None:
        self._relay()

    def do_DELETE(self) -> None:
        self._relay()

    def do_PATCH(self) -> None:
        self._relay()

    def do_HEAD(self) -> None:
        self._relay()

    def do_OPTIONS(self) -> None:
        self._relay()

    def log_message(self, format: str, *args: Any) -> None:
        return


def create_handler(args: argparse.Namespace) -> type[RelayServerHandler]:
    class ConfiguredRelayServerHandler(RelayServerHandler):
        upstream_host = args.upstream_host
        upstream_port = args.upstream_port
        upstream_scheme = args.upstream_scheme
        upstream_timeout = args.timeout

    return ConfiguredRelayServerHandler


def main() -> None:
    args = parse_args()
    handler = create_handler(args)
    server = ThreadingHTTPServer((args.listen_host, args.listen_port), handler)
    print(
        "Relay server listening on "
        f"http://{args.listen_host}:{args.listen_port}, "
        f"upstream={args.upstream_scheme}://{args.upstream_host}:{args.upstream_port}"
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
