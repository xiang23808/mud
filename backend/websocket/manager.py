from fastapi import WebSocket
from typing import Dict
import json

class ConnectionManager:
    def __init__(self):
        self.connections: Dict[int, WebSocket] = {}  # user_id -> websocket
    
    async def connect(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        self.connections[user_id] = websocket
    
    def disconnect(self, user_id: int):
        self.connections.pop(user_id, None)
    
    async def send(self, user_id: int, message: dict):
        if ws := self.connections.get(user_id):
            await ws.send_json(message)
    
    async def broadcast(self, message: dict, exclude: int = None):
        for uid, ws in self.connections.items():
            if uid != exclude:
                await ws.send_json(message)

manager = ConnectionManager()