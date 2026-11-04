from datetime import date

from pydantic import BaseModel, ConfigDict


class ScheduleCreateRequest(BaseModel):
    """管理员新增课表。"""

    user_id: int
    class_date: date
    period: str
    course_id: int
    location: str | None = None


class ScheduleUpdateRequest(BaseModel):
    """管理员修改课表，字段均可选。"""

    user_id: int | None = None
    class_date: date | None = None
    period: str | None = None
    course_id: int | None = None
    location: str | None = None


class ScheduleResponse(BaseModel):
    """课表返回数据：联表带出学生名与课程名。"""

    id: int
    user_id: int
    user_name: str | None = None
    class_date: date
    period: str
    course_id: int
    course_name: str | None = None
    course_code: str | None = None
    location: str | None = None

    model_config = ConfigDict(from_attributes=True)
