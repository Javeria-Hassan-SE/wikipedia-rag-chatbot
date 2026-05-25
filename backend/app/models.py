from typing import List

from pydantic import BaseModel


class IngestRequest(BaseModel):
    url: str


class IngestResponse(BaseModel):
    title: str
    summary: str


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    question: str
    history: List[ChatMessage] = []


class ChatResponse(BaseModel):
    answer: str


class HealthResponse(BaseModel):
    status: str
