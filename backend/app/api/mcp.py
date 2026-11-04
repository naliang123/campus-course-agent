from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.common.response import Response
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.services import mcp_client_service

router = APIRouter(prefix="/mcp", tags=["MCP服务调试"])


@router.get("/my-schedule")
async def get_my_schedule_by_mcp(
    request: Request,
    _current_user: Annotated[User, Depends(get_current_user)],
    date: Annotated[str | None, Query(description="YYYY-MM-DD，不传返回全部")] = None,
):
    """调试通道：只转发请求头里的 Bearer，不把 user_id 传给 MCP。"""
    authorization = request.headers.get("Authorization") or ""
    data = await mcp_client_service.call_get_my_schedules(authorization, date)
    return Response.success(data=data)
