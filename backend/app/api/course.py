from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.common.response import Response
from app.database import get_db
from app.dependencies.auth import get_current_admin
from app.models.user import User
from app.schemas.course import CourseCreateRequest, CourseUpdateRequest
from app.services import course_service

router = APIRouter(prefix="/courses", tags=["课程相关的API接口"])


@router.get("")
def list_courses(
    keywords: str | None = Query(default=None, description="按名称/编码/简介模糊查询"),
    _current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return Response.success(data=course_service.list_courses(db, keywords))


@router.get("/{course_id}")
def get_course(
    course_id: int,
    _current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return Response.success(data=course_service.get_course(db, course_id))


@router.post("")
def create_course(
    data: CourseCreateRequest,
    _current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return Response.success(data=course_service.create_course(db, data))


@router.put("/{course_id}")
def update_course(
    course_id: int,
    data: CourseUpdateRequest,
    _current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return Response.success(data=course_service.update_course(db, course_id, data))


@router.delete("/{course_id}")
def delete_course(
    course_id: int,
    _current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    course_service.delete_course(db, course_id)
    return Response.success()
