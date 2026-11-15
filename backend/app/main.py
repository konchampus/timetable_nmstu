from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import DBAPIError
from .api import router
from .config import config
from .db import engine
from .http_limits import BodyLimitMiddleware, TrustedHostJSONMiddleware
from .games.router import router as game_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(title="Неофициальное расписание МГТУ", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=config.allowed_origins, allow_credentials=False, allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Authorization", "Content-Type"])
app.add_middleware(BodyLimitMiddleware)
app.add_middleware(TrustedHostJSONMiddleware, allowed_hosts=config.allowed_hosts)
app.include_router(router, prefix="/api")
app.include_router(game_router, prefix="/api")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    length = request.headers.get("content-length")
    if length and (not length.isdigit() or int(length) > 65536):
        return JSONResponse({"detail": "Тело запроса слишком велико"}, status_code=413, headers={"Cache-Control": "no-store"})
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors https://web.telegram.org https://*.telegram.org"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    # Pydantic's default errors may echo initData/notes. Never return input values.
    return JSONResponse({"detail": {"message": "Некорректные параметры запроса", "code": "validation_error"}}, status_code=422)


@app.exception_handler(StarletteHTTPException)
async def http_error(request, exc):
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers)


@app.exception_handler(DBAPIError)
async def database_error(request, exc):
    code = getattr(exc.orig, "sqlstate", None)
    if code in ("40001", "40P01", "55P03", "57014"):
        return JSONResponse({"detail": {"message": "Конкурентное изменение; повторите действие", "code": "retry_transaction"}}, status_code=409)
    logging.getLogger(__name__).error("Database operation failed (%s)", type(exc).__name__)
    return JSONResponse({"detail": "Хранилище временно недоступно"}, status_code=503)


@app.exception_handler(Exception)
async def unexpected_error(request, exc):
    logging.getLogger(__name__).error("Request failed (%s)", type(exc).__name__)
    return JSONResponse({"detail": "Внутренняя ошибка сервиса"}, status_code=500)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
