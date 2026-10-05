import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.domain.calls.state import active_call_store

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

router = APIRouter()


@router.websocket("/ws/call/{call_id}")
async def frontend_websocket(websocket: WebSocket, call_id: str):
    """WebSocket for frontend to receive live transcript and suggestions."""
    await websocket.accept()
    logger.info(f"[FRONTEND WS] Connected for call: {call_id}")

    if call_id not in active_call_store:
        active_call_store.set(
            call_id,
            {
                "frontend_ws": websocket,
                "transcript": "",
                "suggestions": [],
            },
        )
    else:
        # Reconnect: preserve existing transcript, just update the ws reference
        active_call_store.update(call_id, frontend_ws=websocket)

    async def ping_loop():
        """Send periodic pings to keep the connection alive."""
        try:
            while True:
                await asyncio.sleep(5)
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                else:
                    break
        except Exception:
            pass

    ping_task = asyncio.create_task(ping_loop())

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "change_provider":
                active_call_store.update(call_id, ai_provider=msg.get("provider", "groq"))
            elif msg.get("type") == "end_call":
                logger.info(f"[FRONTEND WS] End call signal for: {call_id}")
                break
            elif msg.get("type") == "pong":
                pass  # keepalive response from client
    except WebSocketDisconnect:
        logger.info(f"[FRONTEND WS] Disconnected for call: {call_id}")
    except Exception as e:
        logger.error(f"[FRONTEND WS] Error for call {call_id}: {e}")
    finally:
        ping_task.cancel()
        # Don't pop the store - frontend may reconnect
        active_call_store.update(call_id, frontend_ws=None)
