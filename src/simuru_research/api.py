from __future__ import annotations

from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from simuru_research.config.settings import Settings
from simuru_research.security.auth_qa import LocalAuthQAService, QAAuthError

settings = Settings.from_env()
auth_service = LocalAuthQAService(settings.database_path)

@app.middleware("http")
async def enforce_loopback_only(request: Request, call_next):
    client_host = request.client.host if request.client else ""
    if client_host not in {"127.0.0.1", "::1", "localhost", "testclient"}:
        return JSONResponse(
            status_code=403,
            content={"detail": "This QA API is restricted to the local machine."},
        )
    return await call_next(request)


app = FastAPI(
    title="Simuru Local Registration QA API",
    version="0.5.0",
    description=(
        "Loopback-only QA API for testing registration, email/SMS verification, "
        "and login in the team's own local application. It does not connect to Instagram."
    ),
)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=30)
    email: str
    phone: str
    password: str = Field(min_length=12, max_length=128)


class VerifyRequest(BaseModel):
    channel: Literal["email", "sms"]
    destination: str
    code: str = Field(min_length=6, max_length=6)


class LoginRequest(BaseModel):
    email: str
    password: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "simuru-local-registration-qa"}


@app.post("/auth/register", status_code=201)
def register(payload: RegisterRequest) -> dict[str, str]:
    try:
        user_id = auth_service.register_user(
            username=payload.username,
            email=payload.email,
            phone=payload.phone,
            password=payload.password,
        )
    except QAAuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"user_id": user_id, "status": "verification_pending"}


@app.post("/auth/verify")
def verify(payload: VerifyRequest) -> dict[str, str]:
    try:
        auth_service.verify_code(
            channel=payload.channel,
            destination=payload.destination,
            code=payload.code,
        )
    except QAAuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"status": "verified", "channel": payload.channel}


@app.get("/qa/outbox/{channel}")
def read_local_test_outbox(
    channel: Literal["email", "sms"],
    destination: str,
    request: Request,
) -> dict[str, str]:
    client_host = request.client.host if request.client else ""
    if client_host not in {"127.0.0.1", "::1", "localhost", "testclient"}:
        raise HTTPException(
            status_code=403,
            detail="The QA outbox is available only from the local machine.",
        )

    try:
        code = auth_service.get_test_code(
            channel=channel,
            destination=destination,
        )
    except QAAuthError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "channel": channel,
        "destination": destination,
        "code": code,
        "source": "local_test_outbox",
    }


@app.post("/auth/login")
def login(payload: LoginRequest) -> dict[str, str | int]:
    try:
        token = auth_service.login(email=payload.email, password=payload.password)
    except QAAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 3600,
    }


@app.get("/auth/me")
def me(request: Request) -> dict[str, object]:
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Bearer token is required.")

    try:
        return auth_service.authenticate(token.strip())
    except QAAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
