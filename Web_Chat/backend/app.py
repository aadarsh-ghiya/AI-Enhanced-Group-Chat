import os
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from jose import JWTError
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from db import Base, engine, get_session
from auth import (
    auth_header_to_token,
    create_access_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from llm import generate_reply
from models import Message, User

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(str(BASE_DIR / ".env"))

FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(title="AI Enhanced Group Chat")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


class SignupIn(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=128)


class LoginIn(BaseModel):
    username: str
    password: str


class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class MessageOut(BaseModel):
    id: int
    username: str
    content: str
    is_bot: bool
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ConnectionManager:
    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active:
            self.active.remove(websocket)

    async def broadcast(self, payload: dict):
        stale = []
        for socket in self.active:
            try:
                await socket.send_text(json.dumps(payload, default=str))
            except Exception:
                stale.append(socket)
        for socket in stale:
            self.disconnect(socket)


manager = ConnectionManager()


async def get_current_user(
    session: AsyncSession = Depends(get_session),
    authorization: Optional[str] = Header(default=None),
):
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
        )

    token = auth_header_to_token(authorization)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header",
        )

    try:
        payload = decode_token(token)
        username = payload.get("sub")
        if not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    result = await session.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user


@app.on_event("startup")
async def startup():
    auto_create = os.getenv("AUTO_CREATE_TABLES", "1") == "1"
    if auto_create:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)


@app.get("/")
async def index():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.post("/api/auth/signup", response_model=TokenOut)
async def signup(payload: SignupIn, session: AsyncSession = Depends(get_session)):
    username = payload.username.strip()

    existing = await session.execute(select(User).where(User.username == username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already exists")

    user = User(username=username, password_hash=get_password_hash(payload.password))
    session.add(user)
    await session.commit()
    await session.refresh(user)

    token = create_access_token({"sub": user.username})
    return TokenOut(access_token=token)


@app.post("/api/auth/login", response_model=TokenOut)
async def login(payload: LoginIn, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(User).where(User.username == payload.username.strip()))
    user = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": user.username})
    return TokenOut(access_token=token)


@app.get("/api/me")
async def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "username": user.username}


@app.get("/api/messages", response_model=list[MessageOut])
async def list_messages(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Message).order_by(desc(Message.created_at), desc(Message.id)).limit(100)
    )
    rows = list(reversed(result.scalars().all()))
    return [
        MessageOut(
            id=m.id,
            username=m.username,
            content=m.content,
            is_bot=m.is_bot,
            created_at=m.created_at,
        )
        for m in rows
    ]


async def store_message(session: AsyncSession, user: User, content: str, is_bot: bool = False) -> Message:
    msg = Message(
        user_id=user.id,
        username=user.username if not is_bot else "Llama",
        content=content,
        is_bot=is_bot,
    )
    session.add(msg)
    await session.commit()
    await session.refresh(msg)
    return msg


@app.post("/api/messages", response_model=MessageOut)
async def post_message(
    payload: MessageIn,
    session: AsyncSession = Depends(get_session),
    authorization: Optional[str] = Header(default=None),
):
    token = auth_header_to_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Missing authorization token")

    try:
        username = decode_token(token).get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    result = await session.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    username_value = user.username
    message = await store_message(session, user, payload.content, is_bot=False)
    out = MessageOut(
        id=message.id,
        username=message.username,
        content=message.content,
        is_bot=message.is_bot,
        created_at=message.created_at,
    )
    await manager.broadcast({"type": "message", "message": out.model_dump(mode="json")})

    if "?" in payload.content:
        history_result = await session.execute(
            select(Message).order_by(desc(Message.created_at), desc(Message.id)).limit(12)
        )
        history_rows = list(reversed(history_result.scalars().all()))
        history = []
        for h in history_rows:
            role = "assistant" if h.is_bot else "user"
            history.append({"role": role, "content": f"{h.username}: {h.content}"})

        bot_text = await generate_reply(payload.content, username_value, history=history)
        bot_msg = await store_message(session, user, bot_text, is_bot=True)
        bot_out = MessageOut(
            id=bot_msg.id,
            username=bot_msg.username,
            content=bot_msg.content,
            is_bot=bot_msg.is_bot,
            created_at=bot_msg.created_at,
        )
        await manager.broadcast({"type": "message", "message": bot_out.model_dump(mode="json")})

    return out


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)
        return

    try:
        username = decode_token(token).get("sub")
    except JWTError:
        await websocket.close(code=1008)
        return

    if not username:
        await websocket.close(code=1008)
        return

    await manager.connect(websocket)
    try:
        await websocket.send_text(json.dumps({"type": "system", "message": f"Connected as {username}"}))
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)