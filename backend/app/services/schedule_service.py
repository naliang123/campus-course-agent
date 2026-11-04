from datetime import date

from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException
from app.common.response import PageResponse
from app.models.course import Course
from app.models.schedule import Schedule
from app.models.user import User
from app.schemas.schedule import ScheduleCreateRequest, ScheduleResponse, ScheduleUpdateRequest


def _joined_query(db: Session):
    """课表联表查询：带出学生姓名、课程名称与代码。"""
    return (
        db.query(Schedule, User.name, Course.name, Course.code)
        .outerjoin(User, Schedule.user_id == User.id)
        .outerjoin(Course, Schedule.course_id == Course.id)
    )


def _to_response(row) -> ScheduleResponse:
    schedule, user_name, course_name, course_code = row
    return ScheduleResponse(
        id=schedule.id,
        user_id=schedule.user_id,
        user_name=user_name,
        class_date=schedule.class_date,
        period=schedule.period,
        course_id=schedule.course_id,
        course_name=course_name,
        course_code=course_code,
        location=schedule.location,
    )


def _get_one(db: Session, schedule_id: int) -> ScheduleResponse:
    row = _joined_query(db).filter(Schedule.id == schedule_id).first()
    if not row:
        raise BusinessException(message="课表不存在")
    return _to_response(row)


def list_schedules(
    db: Session,
    user_id: int | None = None,
    class_date: date | None = None,
) -> list[ScheduleResponse]:
    """全量课表（不分页），供 MCP 工具与页面共用。"""
    query = _joined_query(db)
    if user_id is not None:
        query = query.filter(Schedule.user_id == user_id)
    if class_date is not None:
        query = query.filter(Schedule.class_date == class_date)
    rows = query.order_by(Schedule.class_date.asc(), Schedule.period.asc()).all()
    return [_to_response(row) for row in rows]


def list_schedules_page(
    db: Session,
    page: int = 1,
    page_size: int = 10,
    user_id: int | None = None,
    class_date: date | None = None,
) -> PageResponse:
    """HTTP 分页列表：学生只能查自己，管理员可传 user_id / date 筛选。"""
    query = _joined_query(db)
    if user_id is not None:
        query = query.filter(Schedule.user_id == user_id)
    if class_date is not None:
        query = query.filter(Schedule.class_date == class_date)
    total = query.count()
    rows = (
        query.order_by(Schedule.class_date.desc(), Schedule.id.desc())
        .offset((max(page, 1) - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PageResponse(list=[_to_response(row) for row in rows], total=total)


def _validate_relations(db: Session, user_id: int, course_id: int) -> None:
    """只能给学生排课，且课程必须存在。"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise BusinessException(message="学生不存在")
    if user.role != "student":
        raise BusinessException(message="只能为学生安排课表")
    if not db.query(Course.id).filter(Course.id == course_id).first():
        raise BusinessException(message="课程不存在")


def create_schedule(db: Session, data: ScheduleCreateRequest) -> ScheduleResponse:
    """新增课表。"""
    _validate_relations(db, data.user_id, data.course_id)
    period = (data.period or "").strip()
    if not period:
        raise BusinessException(message="节次不能为空")
    row = Schedule(
        user_id=data.user_id,
        class_date=data.class_date,
        period=period,
        course_id=data.course_id,
        location=(data.location or "").strip() or None,
    )
    db.add(row)
    db.commit()
    return _get_one(db, row.id)


def update_schedule(
    db: Session, schedule_id: int, data: ScheduleUpdateRequest
) -> ScheduleResponse:
    """修改课表。"""
    row = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not row:
        raise BusinessException(message="课表不存在")
    payload = data.model_dump(exclude_none=True)
    user_id = payload.get("user_id", row.user_id)
    course_id = payload.get("course_id", row.course_id)
    _validate_relations(db, user_id, course_id)
    if "period" in payload:
        payload["period"] = (payload["period"] or "").strip()
        if not payload["period"]:
            raise BusinessException(message="节次不能为空")
    if "location" in payload:
        payload["location"] = (payload["location"] or "").strip() or None
    for field, value in payload.items():
        setattr(row, field, value)
    db.commit()
    return _get_one(db, schedule_id)


def delete_schedule(db: Session, schedule_id: int) -> None:
    """删除课表。"""
    row = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not row:
        raise BusinessException(message="课表不存在")
    db.delete(row)
    db.commit()


def list_schedules_as_dict(
    db: Session,
    user_id: int | None = None,
    date_str: str | None = None,
) -> list[dict]:
    """MCP 工具用：日期转字符串，返回普通字典列表。"""
    date_text = (date_str or "").strip()
    try:
        class_date = date.fromisoformat(date_text) if date_text else None
    except ValueError:
        raise BusinessException(message="日期格式应为 YYYY-MM-DD")
    items = list_schedules(db, user_id, class_date)
    return [
        {
            "date": item.class_date.isoformat(),
            "period": item.period,
            "course_id": item.course_id,
            "course_name": item.course_name,
            "location": item.location,
        }
        for item in items
    ]
