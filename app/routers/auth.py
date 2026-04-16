from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth_utils import create_access_token, hash_password, verify_password
from app.database import get_db
from app.deps import get_current_user_optional
from app.models import User
from app.schemas import UserLogin, UserRegister

router = APIRouter(tags=["auth"])


@router.get("/login", name="login_page")
def login_page(
    request: Request,
    user: Annotated[User | None, Depends(get_current_user_optional)],
):
    if user:
        return RedirectResponse(url="/dashboard", status_code=303)
    return request.app.state.templates.TemplateResponse(
        "login.html",
        {"request": request, "error": None},
    )


@router.post("/login", name="login_submit")
def login_submit(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    email: str = Form(...),
    password: str = Form(...),
):
    try:
        creds = UserLogin(email=email, password=password)
    except ValidationError:
        return request.app.state.templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid email or password format."},
            status_code=422,
        )
    u = db.scalars(select(User).where(User.email == creds.email)).first()
    if not u or not verify_password(creds.password, u.hashed_password):
        return request.app.state.templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Incorrect email or password."},
            status_code=401,
        )
    token = create_access_token(u.id)
    resp = RedirectResponse(url="/dashboard", status_code=303)
    resp.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=60 * 60 * 24 * 7,
        samesite="lax",
    )
    return resp


@router.get("/register", name="register_page")
def register_page(
    request: Request,
    user: Annotated[User | None, Depends(get_current_user_optional)],
):
    if user:
        return RedirectResponse(url="/dashboard", status_code=303)
    return request.app.state.templates.TemplateResponse(
        "register.html",
        {"request": request, "error": None},
    )


@router.post("/register", name="register_submit")
def register_submit(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    email: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(...),
):
    try:
        data = UserRegister(email=email, password=password, full_name=full_name)
    except ValidationError as e:
        err = e.errors()
        msg = err[0].get("msg", "Please check your input.") if err else "Please check your input."
        return request.app.state.templates.TemplateResponse(
            "register.html",
            {"request": request, "error": msg},
            status_code=422,
        )
    if db.scalars(select(User).where(User.email == data.email)).first():
        return request.app.state.templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Email already registered."},
            status_code=400,
        )
    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(user.id)
    resp = RedirectResponse(url="/dashboard", status_code=303)
    resp.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=60 * 60 * 24 * 7,
        samesite="lax",
    )
    return resp


@router.post("/logout", name="logout")
def logout():
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie("access_token")
    return resp


@router.get("/logout")
def logout_get():
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie("access_token")
    return resp
