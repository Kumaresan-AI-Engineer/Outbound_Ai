import time
import logging
import uuid
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from app.routers import contacts, calls, ws, media_stream, clients, projects
from app.database import ensure_indexes

logger = logging.getLogger("outbound")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Paths to skip logging (noisy polling / websocket endpoints)
SKIP_LOG_PATHS = {"/calls/live", "/health", "/ws/call", "/calls/media-stream"}


class RequestLoggerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip noisy endpoints
        path = request.url.path
        if any(path.startswith(s) for s in SKIP_LOG_PATHS):
            return await call_next(request)

        request_id = uuid.uuid4().hex[:8]
        method = request.method
        client = request.client.host if request.client else "unknown"
        start = time.perf_counter()

        logger.info(f"[{request_id}] → {method} {path} from {client}")

        try:
            response = await call_next(request)
            elapsed = (time.perf_counter() - start) * 1000
            status = response.status_code
            level = logging.WARNING if status >= 400 else logging.INFO
            logger.log(level, f"[{request_id}] ← {status} {method} {path} ({elapsed:.0f}ms)")
            return response
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            logger.error(f"[{request_id}] ✗ {method} {path} ({elapsed:.0f}ms) ERROR: {exc}")
            raise


app = FastAPI(title="Outbound Call Assistant", version="1.0.0")

app.add_middleware(RequestLoggerMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(contacts.router)
app.include_router(calls.router)
app.include_router(ws.router)
app.include_router(media_stream.router)
app.include_router(clients.router)
app.include_router(projects.router)


@app.on_event("startup")
async def startup():
    await ensure_indexes()


@app.get("/health")
async def health():
    return {"status": "ok"}


# Serve the built React app (frontend/dist) so the whole site is reachable
# through this same backend origin - i.e. through the one ngrok tunnel.
# Mounted last so it only catches requests the API routers above didn't.
FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
