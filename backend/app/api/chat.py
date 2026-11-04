from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.common.response import Response
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.chat import ChatRequest
from app.services import agent_service

router = APIRouter(prefix="/chat", tags=["AI 对话"])


@router.post("/ask")
async def ask(
    body: ChatRequest,
    request: Request,
    _current_user: Annotated[User, Depends(get_current_user)],
):
    """一次性返回完整回答，供调试与核对工具调用结果。"""
    authorization = request.headers.get("Authorization") or ""
    data = await agent_service.ask(body.question, body.history, authorization)
    return Response.success(data=data)


@router.post("/stream")
async def stream(
    body: ChatRequest,
    request: Request,
    _current_user: Annotated[User, Depends(get_current_user)],
):
    """SSE 流式对话：data: JSON，逐条推送状态、工具过程与回答。"""
    authorization = request.headers.get("Authorization") or ""
    return StreamingResponse(
        agent_service.stream_ask(body.question, body.history, authorization),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
