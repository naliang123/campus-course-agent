from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException
from app.common.response import Response
from app.database import get_db
from app.dependencies.auth import get_current_admin, get_current_user
from app.models.user import User
from app.schemas.schedule import ScheduleCreateRequest, ScheduleUpdateRequest
from app.services import schedule_service

router = APIRouter(prefix="/schedules", tags=["课表相关的API接口"])


def _parse_date(date_str: str | None) -> date | None:
    if not date_str:
        return None
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        raise BusinessException(message="日期格式应为 YYYY-MM-DD")


@router.get("")
def list_schedules(
    page: int = 1,
    page_size: int = 10,
    date: str | None = Query(default=None, description="YYYY-MM-DD，不传查全部"),
    user_id: int | None = Query(default=None, description="仅管理员可用，按学生筛选"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # 学生固定查本人，忽略客户端传来的 user_id，避免越权
    target_user_id = user_id if current_user.role == "admin" else current_user.id
    data = schedule_service.list_schedules_page(
        db,
        page=page,
        page_size=page_size,
        user_id=target_user_id,
        class_date=_parse_date(date),
    )
    return Response.success(data=data)


@router.post("")
def create_schedule(
    data: ScheduleCreateRequest,
    _current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return Response.success(data=schedule_service.create_schedule(db, data))


@router.put("/{schedule_id}")
def update_schedule(
    schedule_id: int,
    data: ScheduleUpdateRequest,
    _current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return Response.success(data=schedule_service.update_schedule(db, schedule_id, data))


@router.delete("/{schedule_id}")
def delete_schedule(
    schedule_id: int,
    _current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    schedule_service.delete_schedule(db, schedule_id)
    return Response.success()
