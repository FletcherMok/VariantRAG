"""Local-browser boundary and bounded request intake before multipart parsing."""

import tempfile

from starlette.responses import JSONResponse

ALLOWED_ORIGINS = {
    f"http://{host}:{port}" for host in ("localhost", "127.0.0.1", "[::1]") for port in (3000, 8000)
}


class LocalBoundary:
    def __init__(self, app, max_bytes=42 * 1024 * 1024):
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        origin = headers.get(b"origin", b"").decode("latin-1")
        if (origin and origin not in ALLOWED_ORIGINS) or (
            not origin
            and scope["path"].startswith("/api/")
            and headers.get(b"sec-fetch-site") == b"cross-site"
        ):
            return await JSONResponse({"detail": "Untrusted browser origin"}, 403)(scope, receive, send)
        if scope["method"] not in {"POST", "PUT", "PATCH"}:
            return await self.app(scope, receive, send)
        try:
            length = int(headers.get(b"content-length", b"0"))
        except ValueError:
            return await JSONResponse({"detail": "Invalid Content-Length"}, 400)(scope, receive, send)
        if length > self.max_bytes:
            return await JSONResponse({"detail": "Request exceeds 42 MiB"}, 413)(scope, receive, send)
        # Spool before Starlette parses multipart files: its UploadFile has already
        # received the body by the time an endpoint's file-size check executes.
        with tempfile.SpooledTemporaryFile(max_size=1024 * 1024) as body:
            size = 0
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                chunk = message.get("body", b"")
                size += len(chunk)
                if size > self.max_bytes:
                    return await JSONResponse({"detail": "Request exceeds 42 MiB"}, 413)(scope, receive, send)
                body.write(chunk)
                if not message.get("more_body", False):
                    break
            body.seek(0)

            async def bounded_receive():
                chunk = body.read(64 * 1024)
                return {"type": "http.request", "body": chunk, "more_body": body.tell() < size}

            return await self.app(scope, bounded_receive, send)
