# models.py
from pydantic import BaseModel
from typing import List, Dict, Optional

class ChatRequest(BaseModel):
    session_id: str
    message: str

class ChatResponse(BaseModel):
    reply: str
    tool_calls: List[dict] = []
    state: Optional[Dict] = None