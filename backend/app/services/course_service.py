from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException
from app.models.course import Course
from app.models.schedule import Schedule
from app.schemas.course import (
    CourseCreateRequest,
    CourseResponse,
    CourseUpdateRequest,
)


def list_courses(db: Session, keywords: str | None = None) -> list[CourseResponse]:
    """课程列表，可按名称 / 编码 / 简介模糊查询。"""
    query = db.query(Course)
    if keywords and keywords.strip():
        kw = f"%{keywords.strip()}%"
        query = query.filter(
            or_(
                Course.name.ilike(kw),
                Course.code.ilike(kw),
                Course.description.ilike(kw),
            )
        )
    rows = query.order_by(Course.id.desc()).all()
    return [CourseResponse.model_validate(row) for row in rows]


def get_course(db: Session, course_id: int) -> CourseResponse:
    """课程详情。"""
    row = db.query(Course).filter(Course.id == course_id).first()
    if not row:
        raise BusinessException(message="课程不存在")
    return CourseResponse.model_validate(row)


def create_course(db: Session, data: CourseCreateRequest) -> CourseResponse:
    """新增课程：代码必填且有值时唯一。"""
    name = (data.name or "").strip()
    code = (data.code or "").strip()
    if not name:
        raise BusinessException(message="课程名称必传")
    if not code:
        raise BusinessException(message="课程编码必传")
    if db.query(Course).filter(Course.code == code).first():
        raise BusinessException(message="课程代码已存在")
    course = Course(
        name=name,
        code=code,
        description=(data.description or "").strip() or None,
        status=data.status if data.status in (0, 1) else 1,
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return CourseResponse.model_validate(course)


def update_course(
    db: Session, course_id: int, data: CourseUpdateRequest
) -> CourseResponse:
    """更新课程。"""
    row = db.query(Course).filter(Course.id == course_id).first()
    if not row:
        raise BusinessException(message="课程不存在")
    payload = data.model_dump(exclude_none=True)
    if "name" in payload:
        payload["name"] = (payload["name"] or "").strip()
        if not payload["name"]:
            raise BusinessException(message="课程名称必传")
    if "code" in payload:
        code = (payload["code"] or "").strip()
        if not code:
            raise BusinessException(message="课程编码必传")
        conflict = (
            db.query(Course)
            .filter(Course.code == code, Course.id != course_id)
            .first()
        )
        if conflict:
            raise BusinessException(message="课程编号已存在")
        payload["code"] = code
    if "description" in payload:
        payload["description"] = (payload["description"] or "").strip() or None
    if "status" in payload and payload["status"] not in (0, 1):
        payload["status"] = 1
    for field, value in payload.items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return CourseResponse.model_validate(row)


def delete_course(db: Session, course_id: int) -> None:
    """删除课程；已关联课表的课程不可删。"""
    row = db.query(Course).filter(Course.id == course_id).first()
    if not row:
        raise BusinessException(message="课程不存在")
    linked = db.query(Schedule.id).filter(Schedule.course_id == course_id).first()
    if linked:
        raise BusinessException(message="该课程已关联课表，无法删除")
    db.delete(row)
    db.commit()
