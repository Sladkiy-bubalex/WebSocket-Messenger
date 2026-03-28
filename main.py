import json
import weakref
import time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.websockets import WebSocketState
from dataclasses import dataclass
from loguru import logger
from typing import Optional


app = FastAPI()
templates = Jinja2Templates(directory="templates")


@dataclass
class ConnectionInfo:
    """
    Класс для хранения информации о конкретном WebSocket соединении
    """
    websocket: WebSocket
    message_counter: int = 0
    manager_ref: Optional[weakref.ReferenceType] = None
    
    def get_next_number(self) -> int:
        """Увеличивает счетчик и возвращает новое значение"""
        self.message_counter += 1
        return self.message_counter
    
    def reset_counter(self):
        """Сбрасывает счетчик"""
        self.message_counter = 0


class ConnectionManager:
    def __init__(self):
        self._connections: dict[int, ConnectionInfo] = {}

    async def connect(self, websocket: WebSocket) -> ConnectionInfo:
        await websocket.accept()

        connection_info = ConnectionInfo(websocket=websocket)
        self._connections[id(websocket)] = connection_info

        logger.info(f"[CONNECT] Active connections: {self.active_count}")
        return connection_info

    async def disconnect(self, websocket: WebSocket):
        ws_id = id(websocket)

        if ws_id in self._connections:
            del self._connections[ws_id]

        if websocket.client_state == WebSocketState.CONNECTED:
            try:
                await websocket.close()
            except Exception:
                pass
        logger.info(f"[DISCONNECT] Active connections: {self.active_count}")

    async def send_message(self, message: dict, websocket: WebSocket) -> bool:
        if id(websocket) not in self._connections:
            return False

        try:
            await websocket.send_json(message)
            return True
        except Exception as e:
            logger.error(f"Ошибка отправки: {e}")
            await self.disconnect(websocket)
            return False

    @property
    def active_count(self) -> int:
        return len(self._connections)


manager = ConnectionManager()


@app.get("/", response_class=HTMLResponse)
async def get_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={}
    )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    connection_info = await manager.connect(websocket)

    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)

            if message_data.get("type") == "ping":
                continue

            user_message = message_data.get("message", "").strip()

            if not user_message:
                continue

            if len(user_message) > 1000:
                continue

            message_number = connection_info.get_next_number()

            response = {
                "number": message_number,
                "text": user_message,
                "timestamp": time.time()
            }

            await manager.send_message(response, websocket)

    except WebSocketDisconnect:
        logger.info(f"Клиент отключился в WebSocket {websocket}")

    except Exception as e:
        logger.error(f"Ошибка в WebSocket {websocket}: {e}")

    finally:
        await manager.disconnect(websocket)
