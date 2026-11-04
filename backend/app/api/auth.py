from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from app.common.exceptions import BusinessException
from app.common.response import Response
from app.schemas.auth import LoginRequest
from app.schemas.auth import RegisterRequest
from sqlalchemy.orm import Session
from app.database import get_db
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["权限验证"])


@router.post("/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    """登录"""
    result = auth_service.login(db, data)
    # 返回信息
    return Response.success(
        message="登录成功",
        data=result,
    )


@router.post("/register")
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    """注册"""
    auth_service.register(db, data)
    # 返回信息
    return Response.success(message="注册成功")


@router.post("/token", include_in_schema=False)
def token(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Session = Depends(get_db),
):
    """Swagger「Authorize」专用：符合 OAuth2 password 规范。

    前端仍走 /login 的 JSON 登录；本端点把表单账号密码转成同一套登录业务，
    并返回标准 access_token / token_type，client_id 与 client_secret 不校验。
    """
    try:
        result = auth_service.login(
            db, LoginRequest(username=form.username, password=form.password)
        )
    except BusinessException as exc:
        return JSONResponse(
            status_code=400,
            content=Response.error(code=exc.code, message=exc.message).model_dump(),
        )
    return {"access_token": result.token, "token_type": "bearer"}
