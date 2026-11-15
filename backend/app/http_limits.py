from urllib.parse import urlsplit
from starlette.responses import JSONResponse


class TrustedHostJSONMiddleware:
    def __init__(self, app, allowed_hosts):
        self.app = app
        self.allowed_hosts = {host.casefold() for host in allowed_hosts}

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        try:
            host = urlsplit("//" + headers.get(b"host", b"").decode("ascii")).hostname
        except (ValueError, UnicodeError):
            host = None
        if not host or host.casefold() not in self.allowed_hosts:
            if scope["type"] == "websocket":
                return await send({"type": "websocket.close", "code": 1008})
            response = JSONResponse({"detail": "Недопустимый Host"}, status_code=400, headers={"Cache-Control": "no-store"})
            return await response(scope, receive, send)
        await self.app(scope, receive, send)


class BodyLimitMiddleware:
    """Bound decoded request bytes, including chunked requests without Content-Length."""
    def __init__(self, app, max_bytes=65536):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        content = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            content.extend(message.get("body", b""))
            if len(content) > self.max_bytes:
                response = JSONResponse({"detail": "Тело запроса слишком велико"}, status_code=413, headers={"Cache-Control": "no-store"})
                return await response(scope, receive, send)
            if not message.get("more_body", False):
                break
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(content), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)
