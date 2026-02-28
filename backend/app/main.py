from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import contacts, calls, ws, media_stream

app = FastAPI(title="Outbound Call Assistant", version="1.0.0")

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


@app.get("/health")
async def health():
    return {"status": "ok"}
