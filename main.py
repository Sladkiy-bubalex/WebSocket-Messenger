import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from dataclasses import dataclass
from loguru import logger


app = FastAPI()
templates = Jinja2Templates(directory="templates")


@dataclass
class ConnectionInfo:
    """
    Класс для хранения информации о конкретном WebSocket соединении
    """
    websocket: WebSocket
    message_counter: int = 0
    
    def get_next_number(self) -> int:
        """Увеличивает счетчик и возвращает новое значение"""
        self.message_counter += 1
        return self.message_counter
    
    def reset_counter(self):
        """Сбрасывает счетчик"""
        self.message_counter = 0


class ConnectionManager:
    """
    Менеджер WebSocket соединений
    """

    def __init__(self):
        self._connections: dict[WebSocket, ConnectionInfo] = {}

    async def connect(self, websocket: WebSocket) -> ConnectionInfo:
        """
        Принимает новое WebSocket соединение и возвращает информацию о нем
        """
        await websocket.accept()
        connection_info = ConnectionInfo(websocket=websocket)
        self._connections[websocket] = connection_info
        return connection_info

    def disconnect(self, websocket: WebSocket):
        """Удаляет WebSocket соединение"""
        if websocket in self._connections:
            del self._connections[websocket]

    async def send_message(self, message: dict, websocket: WebSocket):
        """Отправляет JSON сообщение конкретному клиенту"""
        await websocket.send_json(message)

    @property
    def active_count(self) -> int:
        """Возвращает количество активных соединений"""
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
    """WebSocket эндпоинт для обмена сообщениями"""

    connection_info = await manager.connect(websocket)
    logger.info(f"Клиент подключен. Всего соединений: {manager.active_count}")

    try:
        while True:
            data = await websocket.receive_text()

            try:
                message_data = json.loads(data)
                user_message = message_data.get("message", "")

                if user_message:
                    message_number = connection_info.get_next_number()

                    response = {
                        "number": message_number,
                        "text": user_message
                    }

                    await manager.send_message(response, websocket)

            except json.JSONDecodeError:
                logger.error(f"Получен некорректный JSON: {data}")

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info(
            f"Клиент отключен. Осталось соединений: {manager.active_count}"
        )
