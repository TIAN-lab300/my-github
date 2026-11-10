# Smart Learning Planner Platform Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a runnable backend foundation for single-school multi-teacher multi-class operation, including SQLite persistence, local authentication, sessions, RBAC, audit logging, classrooms, invite codes, and object-level data isolation.

**Architecture:** Create a FastAPI modular monolith with explicit API, service, repository, and database layers. SQLite stores users, sessions, audit logs, classrooms, memberships, and invites. Authentication uses Argon2 password hashes and opaque server-side sessions stored as hashes in HttpOnly cookies.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic, Pydantic 2.x, pydantic-settings, SQLite, Argon2, pytest, pytest-asyncio, and HTTPX.

**Spec:**
- `docx/2026-10-27-smart-learning-planner-requirements-spec.md`
- `docx/2026-10-27-smart-learning-planner-design.md`
- `docx/2026-10-27-smart-learning-planner-technical-design.md`

## Program Decomposition

The complete platform is deliberately split into independent plans because each subsystem must produce a testable result on its own.

1. **Platform Foundation:** This plan. Backend scaffold, database, users, sessions, RBAC, audit, classrooms, invites, and isolation tests.
2. **Student AI Core:** Goals, diagnostics, graph snapshots, coverage checks, Qwen gateway, RAG, planning, validation, BKT, and replanning.
3. **Teacher, Resource and Profile Platform:** Teacher tasks, progress analytics, student profile snapshots, class profile snapshots, profile refresh, resources, assessments, grading, and global budgets.
4. **Frontend Application:** Student, teacher, and administrator interfaces plus API integration.
5. **Integration and Acceptance Evidence:** End-to-end tests, AT-001 through AT-030 evidence, deployment, backup, and handoff.

Plan 2 and Plan 3 may proceed in parallel after this plan. Plan 4 starts after the backend API contracts needed by its pages are stable. Plan 5 is always last.

## File Structure

```text
backend/
  pyproject.toml
  alembic.ini
  .env.example
  app/
    __init__.py
    main.py
    api/
      __init__.py
      deps.py
      v1/
        __init__.py
        router.py
        health.py
        auth.py
        admin.py
        classes.py
    core/
      __init__.py
      config.py
      errors.py
      security.py
    db/
      __init__.py
      base.py
      session.py
      models/
        __init__.py
        user.py
        session.py
        audit.py
        classroom.py
    schemas/
      __init__.py
      auth.py
      classroom.py
    services/
      __init__.py
      auth/
        __init__.py
        passwords.py
        sessions.py
        authorization.py
        bootstrap.py
      audit/
        __init__.py
        service.py
      classrooms/
        __init__.py
        service.py
        invites.py
  migrations/
    env.py
    script.py.mako
    versions/
  tests/
    conftest.py
    api/
      test_health.py
      test_auth.py
      test_classes.py
    unit/
      test_passwords.py
      test_bootstrap.py
      test_authorization.py
    integration/
      test_database.py
      test_data_isolation.py
```

## Global Constraints

- Python runtime must be 3.12 or newer and Node.js is not needed for this plan.
- Service binds to `127.0.0.1:8000`.
- API base path is `/api/v1`.
- JSON fields use `snake_case`.
- All timestamps are stored in UTC and serialized as ISO 8601.
- User roles are exactly `admin`, `teacher`, and `student`.
- Passwords are stored only as Argon2 hashes.
- Session tokens are random opaque values; only token hashes are stored in SQLite.
- Session cookies are HttpOnly and SameSite=Lax.
- Mutating requests must pass an Origin/CSRF defense.
- Every protected endpoint must enforce role and object-level class or student ownership.
- Teachers may access only classrooms where `owner_teacher_id` equals their user ID.
- One classroom has exactly one owner teacher; a student may join multiple classrooms.
- First administrator creation is idempotent and reads credentials from environment variables.
- No default password, API key, secret, or real user record is committed.
- The test database uses SQLite foreign keys and forced rollback cleanup.
- A test that has not been run is reported as unverified, never as passing.

---

### Task 1: Bootstrap the Backend and Health Endpoint

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/v1/__init__.py`
- Create: `backend/app/api/v1/router.py`
- Create: `backend/app/api/v1/health.py`
- Create: `backend/app/core/__init__.py`
- Create: `backend/app/core/config.py`
- Create: `backend/tests/api/test_health.py`

**Interfaces:**
- Consumes: Python 3.12 environment.
- Produces: FastAPI application object `app.main.app`; `GET /api/v1/health` returns `{"status": "ok"}`.

- [ ] **Step 1: Write the failing health test**

```python
# backend/tests/api/test_health.py
from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok() -> None:
    response = TestClient(app).get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```powershell
cd backend
python -m pytest tests/api/test_health.py::test_health_returns_ok -v
```

Expected: collection or import failure because `app.main` does not exist.

- [ ] **Step 3: Create the minimal application**

```toml
# backend/pyproject.toml
[project]
name = "smart-learning-planner-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115,<1",
  "uvicorn[standard]>=0.30,<1",
  "sqlalchemy>=2.0,<3",
  "alembic>=1.13,<2",
  "pydantic-settings>=2.4,<3",
  "argon2-cffi>=23.1,<26",
]

[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["app*"]

[project.optional-dependencies]
dev = [
  "httpx>=0.27,<1",
  "pytest>=8.3,<9",
  "pytest-asyncio>=0.24,<1",
]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
addopts = "-q"
```

```python
# backend/app/api/v1/health.py
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

```python
# backend/app/api/v1/router.py
from fastapi import APIRouter

from app.api.v1 import health

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router, tags=["health"])
```

```python
# backend/app/main.py
from fastapi import FastAPI

from app.api.v1.router import api_router

app = FastAPI(title="Smart Learning Planner API")
app.include_router(api_router)
```

Create empty `__init__.py` files in `app`, `app/api`, and `app/api/v1`.

- [ ] **Step 4: Install dependencies and run the test**

Run:

```powershell
cd backend
python -m pip install -e ".[dev]"
python -m pytest tests/api/test_health.py::test_health_returns_ok -v
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```powershell
git add backend/pyproject.toml backend/app backend/tests/api/test_health.py
git commit -m "feat: bootstrap backend health endpoint"
```

---

### Task 2: Configure SQLite Sessions and Foreign-Key Enforcement

**Files:**
- Create: `backend/app/db/__init__.py`
- Create: `backend/app/db/base.py`
- Create: `backend/app/db/session.py`
- Modify: `backend/app/core/config.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/integration/test_database.py`

**Interfaces:**
- Consumes: `app.core.config.Settings`.
- Produces: `Base`, `build_engine(database_url: str)`, `SessionLocal`, `get_db()`.

- [ ] **Step 1: Write the failing database test**

```python
# backend/tests/integration/test_database.py
from sqlalchemy import text

from app.db.session import build_engine


def test_sqlite_foreign_keys_are_enabled(tmp_path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```powershell
cd backend
python -m pytest tests/integration/test_database.py -v
```

Expected: import failure for `app.db.session`.

- [ ] **Step 3: Implement settings and SQLAlchemy session**

```python
# backend/app/core/config.py
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    database_url: str = "sqlite:///./smart_learning.db"
    session_cookie_name: str = "slp_session"
    session_ttl_hours: int = 12
    allowed_origin: str = "http://127.0.0.1:8000"
    bootstrap_admin_username: str | None = None
    bootstrap_admin_password: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

```python
# backend/app/db/base.py
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

```python
# backend/app/db/session.py
from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def _enable_sqlite_pragmas(dbapi_connection, connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


def build_engine(database_url: str) -> Engine:
    engine = create_engine(database_url, future=True)
    event.listen(engine, "connect", _enable_sqlite_pragmas)
    return engine


engine = build_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
```

- [ ] **Step 4: Run the database test**

Run:

```powershell
cd backend
python -m pytest tests/integration/test_database.py::test_sqlite_foreign_keys_are_enabled -v
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/core/config.py backend/app/db backend/tests/integration/test_database.py
git commit -m "feat: configure sqlite session infrastructure"
```

---

### Task 3: Add Users, Roles, and Argon2 Password Hashing

**Files:**
- Create: `backend/app/db/models/__init__.py`
- Create: `backend/app/db/models/user.py`
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/auth/__init__.py`
- Create: `backend/app/services/auth/passwords.py`
- Create: `backend/tests/unit/test_passwords.py`

**Interfaces:**
- Consumes: SQLAlchemy `Base`.
- Produces: `Role`, `User`, `PasswordService.hash(password)`, `PasswordService.verify(password_hash, password)`.

- [ ] **Step 1: Write the failing password test**

```python
# backend/tests/unit/test_passwords.py
from app.services.auth.passwords import PasswordService


def test_password_hash_is_verifiable_and_not_plaintext() -> None:
    service = PasswordService()
    password_hash = service.hash("ChangeMe-123!")
    assert password_hash != "ChangeMe-123!"
    assert service.verify(password_hash, "ChangeMe-123!") is True
    assert service.verify(password_hash, "wrong") is False
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```powershell
cd backend
python -m pytest tests/unit/test_passwords.py -v
```

Expected: import failure for `PasswordService`.

- [ ] **Step 3: Implement the Role enum, User model, and password service**

```python
# backend/app/db/models/user.py
from datetime import datetime, timezone
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Role(StrEnum):
    ADMIN = "admin"
    TEACHER = "teacher"
    STUDENT = "student"


class UserStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(20), default=UserStatus.ACTIVE.value)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

```python
# backend/app/services/auth/passwords.py
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError


class PasswordService:
    def __init__(self) -> None:
        self._hasher = PasswordHasher()

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password_hash: str, password: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except VerifyMismatchError:
            return False
```

Export `User`, `Role`, and `UserStatus` from `backend/app/db/models/__init__.py`.

- [ ] **Step 4: Run the unit test**

Run:

```powershell
cd backend
python -m pytest tests/unit/test_passwords.py -v
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/db/models backend/app/services/auth/passwords.py backend/tests/unit/test_passwords.py
git commit -m "feat: add users roles and password hashing"
```

---

### Task 4: Create the Idempotent Administrator Bootstrap

**Files:**
- Create: `backend/app/services/auth/bootstrap.py`
- Create: `backend/app/scripts/__init__.py`
- Create: `backend/app/scripts/bootstrap_admin.py`
- Create: `backend/.env.example`
- Create: `backend/tests/unit/test_bootstrap.py`

**Interfaces:**
- Consumes: `Session`, `User`, `Role`, `PasswordService`.
- Produces: `bootstrap_admin(session, username, password) -> User`; second call with same username returns the existing admin without changing its password.

- [ ] **Step 1: Write the failing bootstrap test**

```python
# backend/tests/unit/test_bootstrap.py
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models.user import Role, User
from app.services.auth.bootstrap import bootstrap_admin


def test_bootstrap_admin_is_idempotent() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        first = bootstrap_admin(session, "root-admin", "Strong-Pass-123!")
        second = bootstrap_admin(session, "root-admin", "Different-Pass-456!")
        users = session.scalars(select(User)).all()
        assert len(users) == 1
        assert first.id == second.id
        assert users[0].role == Role.ADMIN.value
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```powershell
cd backend
python -m pytest tests/unit/test_bootstrap.py -v
```

Expected: import failure for `bootstrap_admin`.

- [ ] **Step 3: Implement the bootstrap service and CLI**

```python
# backend/app/services/auth/bootstrap.py
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.user import Role, User, UserStatus
from app.services.auth.passwords import PasswordService


def bootstrap_admin(session: Session, username: str, password: str) -> User:
    existing = session.scalar(select(User).where(User.username == username))
    if existing is not None:
        return existing

    user = User(
        username=username,
        display_name="School Administrator",
        password_hash=PasswordService().hash(password),
        role=Role.ADMIN.value,
        status=UserStatus.ACTIVE.value,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
```

```python
# backend/app/scripts/bootstrap_admin.py
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.auth.bootstrap import bootstrap_admin


def main() -> None:
    settings = get_settings()
    if not settings.bootstrap_admin_username or not settings.bootstrap_admin_password:
        raise SystemExit("BOOTSTRAP_ADMIN_USERNAME and BOOTSTRAP_ADMIN_PASSWORD are required")
    with SessionLocal() as session:
        user = bootstrap_admin(
            session,
            settings.bootstrap_admin_username,
            settings.bootstrap_admin_password,
        )
        print(f"Admin ready: {user.username}")


if __name__ == "__main__":
    main()
```

```dotenv
# backend/.env.example
DATABASE_URL=sqlite:///./smart_learning.db
SESSION_COOKIE_NAME=slp_session
SESSION_TTL_HOURS=12
ALLOWED_ORIGIN=http://127.0.0.1:8000
BOOTSTRAP_ADMIN_USERNAME=
BOOTSTRAP_ADMIN_PASSWORD=
```

- [ ] **Step 4: Run the bootstrap test**

Run:

```powershell
cd backend
python -m pytest tests/unit/test_bootstrap.py::test_bootstrap_admin_is_idempotent -v
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/auth/bootstrap.py backend/app/scripts backend/.env.example backend/tests/unit/test_bootstrap.py
git commit -m "feat: add idempotent admin bootstrap"
```

---

### Task 5: Implement Opaque Server-Side Sessions and Login API

**Files:**
- Create: `backend/app/db/models/session.py`
- Create: `backend/app/services/auth/sessions.py`
- Create: `backend/app/schemas/auth.py`
- Create: `backend/app/api/deps.py`
- Create: `backend/app/api/v1/auth.py`
- Modify: `backend/app/api/v1/router.py`
- Create: `backend/tests/api/test_auth.py`

**Interfaces:**
- Consumes: `User`, `SessionLocal`, `PasswordService`.
- Produces: `SessionService.login(session, username, password) -> tuple[User, str]`; `SessionService.authenticate_token(session, token) -> User | None`; `SessionService.revoke(session, token) -> None`; `POST /api/v1/auth/login`, `POST /api/v1/auth/logout`, `GET /api/v1/auth/me`.

- [ ] **Step 1: Write failing authentication tests**

```python
# backend/tests/api/test_auth.py
from fastapi.testclient import TestClient

from app.main import app


def test_login_me_and_logout_flow(seeded_user) -> None:
    client = TestClient(app)
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "teacher1", "password": "Strong-Pass-123!"},
        headers={"Origin": "http://testserver"},
    )
    assert login.status_code == 200
    assert "slp_session" in login.cookies

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["role"] == "teacher"

    logout = client.post(
        "/api/v1/auth/logout",
        headers={"Origin": "http://testserver"},
    )
    assert logout.status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401
```

Add a `seeded_user` fixture in `backend/tests/conftest.py` that creates tables in a temporary SQLite database, overrides `get_db`, and inserts an active teacher.

- [ ] **Step 2: Run the test and verify it fails**

Run:

```powershell
cd backend
python -m pytest tests/api/test_auth.py -v
```

Expected: route failures for missing auth endpoints.

- [ ] **Step 3: Implement the session model, service, schemas, dependency, and routes**

```python
# backend/app/db/models/session.py
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuthSession(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

```python
# backend/app/services/auth/sessions.py
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.session import AuthSession
from app.db.models.user import User, UserStatus
from app.services.auth.passwords import PasswordService


class SessionService:
    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def login(self, session: Session, username: str, password: str, ttl_hours: int = 12):
        user = session.scalar(select(User).where(User.username == username))
        if user is None or user.status != UserStatus.ACTIVE.value:
            return None
        if not PasswordService().verify(user.password_hash, password):
            return None
        token = secrets.token_urlsafe(32)
        record = AuthSession(
            user_id=user.id,
            token_hash=self._hash_token(token),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=ttl_hours),
        )
        session.add(record)
        session.commit()
        return user, token

    def authenticate_token(self, session: Session, token: str) -> User | None:
        record = session.scalar(
            select(AuthSession).where(AuthSession.token_hash == self._hash_token(token))
        )
        now = datetime.now(timezone.utc)
        if record is None or record.revoked_at is not None or record.expires_at <= now:
            return None
        user = session.get(User, record.user_id)
        return user if user and user.status == UserStatus.ACTIVE.value else None

    def revoke(self, session: Session, token: str) -> None:
        record = session.scalar(
            select(AuthSession).where(AuthSession.token_hash == self._hash_token(token))
        )
        if record is not None and record.revoked_at is None:
            record.revoked_at = datetime.now(timezone.utc)
            session.commit()
```

```python
# backend/app/schemas/auth.py
from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class UserView(BaseModel):
    id: str
    username: str
    display_name: str
    role: str

    model_config = {"from_attributes": True}
```

```python
# backend/app/api/deps.py
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.db.models.user import User
from app.services.auth.sessions import SessionService


def current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    token = request.cookies.get(get_settings().session_cookie_name)
    if not token:
        raise HTTPException(status_code=401, detail={"code": "AUTH_REQUIRED"})
    user = SessionService().authenticate_token(db, token)
    if user is None:
        raise HTTPException(status_code=401, detail={"code": "AUTH_REQUIRED"})
    return user
```

```python
# backend/app/api/v1/auth.py
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.auth import LoginRequest, UserView
from app.services.auth.sessions import SessionService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=UserView)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    result = SessionService().login(
        db, payload.username, payload.password, get_settings().session_ttl_hours
    )
    if result is None:
        raise HTTPException(status_code=401, detail={"code": "AUTH_REQUIRED"})
    user, token = result
    response.set_cookie(
        get_settings().session_cookie_name,
        token,
        httponly=True,
        samesite="lax",
        max_age=get_settings().session_ttl_hours * 3600,
    )
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get(get_settings().session_cookie_name)
    if token:
        SessionService().revoke(db, token)
    response.delete_cookie(get_settings().session_cookie_name)
    return None


@router.get("/me", response_model=UserView)
def me(user=Depends(current_user)):
    return user
```

Add the auth router to `api_router`.

- [ ] **Step 4: Run the auth test**

Run:

```powershell
cd backend
python -m pytest tests/api/test_auth.py -v
```

Expected: all auth tests pass, including logout revoking the server-side session.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/db/models/session.py backend/app/services/auth/sessions.py backend/app/schemas/auth.py backend/app/api/deps.py backend/app/api/v1/auth.py backend/app/api/v1/router.py backend/tests/api/test_auth.py backend/tests/conftest.py
git commit -m "feat: add server-side session login"
```

---

### Task 6: Enforce Origin Checks for Unsafe Requests

**Files:**
- Create: `backend/app/core/errors.py`
- Create: `backend/app/core/middleware.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/api/test_auth.py`

**Interfaces:**
- Consumes: `Settings.allowed_origin`, session cookie.
- Produces: unsafe-method Origin enforcement.

- [ ] **Step 1: Write failing origin and revoke tests**

```python
def test_unsafe_request_with_wrong_origin_is_rejected() -> None:
    response = TestClient(app).post(
        "/api/v1/auth/login",
        json={"username": "teacher1", "password": "Strong-Pass-123!"},
        headers={"Origin": "https://evil.example"},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "ORIGIN_REJECTED"
```

- [ ] **Step 2: Run the tests and verify the new origin test fails**

Run:

```powershell
cd backend
python -m pytest tests/api/test_auth.py -v
```

Expected: the wrong-origin request is not rejected.

- [ ] **Step 3: Implement middleware and token revocation**

```python
# backend/app/core/middleware.py
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import get_settings


class OriginGuardMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("origin")
            if origin != get_settings().allowed_origin:
                return JSONResponse(
                    {"detail": {"code": "ORIGIN_REJECTED"}},
                    status_code=403,
                )
        return await call_next(request)
```

```python
# backend/app/main.py
from app.core.middleware import OriginGuardMiddleware

app.add_middleware(OriginGuardMiddleware)
```

Set the test client origin to `http://testserver` in `tests/conftest.py` or update `Settings.allowed_origin` for tests.

- [ ] **Step 4: Run all auth tests**

Run:

```powershell
cd backend
python -m pytest tests/api/test_auth.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/core backend/app/main.py backend/tests/api/test_auth.py backend/tests/conftest.py
git commit -m "feat: enforce request origin checks"
```

---

### Task 7: Add Audit Logging for Authentication and Security Events

**Files:**
- Create: `backend/app/db/models/audit.py`
- Create: `backend/app/services/audit/__init__.py`
- Create: `backend/app/services/audit/service.py`
- Modify: `backend/app/api/v1/auth.py`
- Modify: `backend/app/api/v1/router.py`
- Create: `backend/tests/integration/test_audit.py`

**Interfaces:**
- Consumes: `Session`, `User`.
- Produces: `AuditService.record(session, actor_user_id, action, target_type, target_id, payload=None)`.

- [ ] **Step 1: Write the failing audit test**

```python
from sqlalchemy import select

from app.db.models.audit import AuditLog
from app.services.audit.service import AuditService


def test_audit_event_is_persisted(db_session) -> None:
    AuditService().record(
        db_session,
        actor_user_id=None,
        action="login_failed",
        target_type="user",
        target_id="unknown",
        payload={"username": "bad-user"},
    )
    event = db_session.scalar(select(AuditLog))
    assert event.action == "login_failed"
    assert event.payload_json == {"username": "bad-user"}
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```powershell
cd backend
python -m pytest tests/integration/test_audit.py -v
```

Expected: import failure for audit modules.

- [ ] **Step 3: Implement audit persistence and record login outcomes**

```python
# backend/app/db/models/audit.py
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    target_type: Mapped[str] = mapped_column(String(40))
    target_id: Mapped[str] = mapped_column(String(80))
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

```python
# backend/app/services/audit/service.py
from sqlalchemy.orm import Session

from app.db.models.audit import AuditLog


class AuditService:
    def record(
        self,
        session: Session,
        *,
        actor_user_id: str | None,
        action: str,
        target_type: str,
        target_id: str,
        payload: dict | None = None,
    ) -> AuditLog:
        event = AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            payload_json=payload or {},
        )
        session.add(event)
        session.commit()
        return event
```

Record `login_succeeded` and `login_failed` without storing the password. Audit records use username or user ID only.

- [ ] **Step 4: Run the audit and auth tests**

Run:

```powershell
cd backend
python -m pytest tests/integration/test_audit.py tests/api/test_auth.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/db/models/audit.py backend/app/services/audit backend/app/api/v1/auth.py backend/app/api/v1/router.py backend/tests/integration/test_audit.py
git commit -m "feat: add authentication audit events"
```

---

### Task 8: Add Classrooms and Student Memberships

**Files:**
- Create: `backend/app/db/models/classroom.py`
- Create: `backend/app/schemas/classroom.py`
- Create: `backend/app/services/classrooms/__init__.py`
- Create: `backend/app/services/classrooms/service.py`
- Create: `backend/app/api/v1/classes.py`
- Modify: `backend/app/api/v1/router.py`
- Create: `backend/tests/api/test_classes.py`

**Interfaces:**
- Consumes: current authenticated `User`.
- Produces: `Classroom`, `ClassMembership`, `ClassroomService.create_class`, `.list_for_user`, `.get_for_teacher`, `.join_student`, `.archive`.

- [ ] **Step 1: Write failing classroom tests**

```python
def test_teacher_can_create_class_and_list_owned_classes(teacher_client) -> None:
    created = teacher_client.post(
        "/api/v1/classes",
        json={"name": "Python 2026", "description": "Backend fundamentals"},
        headers={"Origin": "http://testserver"},
    )
    assert created.status_code == 201
    class_id = created.json()["id"]
    listed = teacher_client.get("/api/v1/classes")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [class_id]


def test_student_cannot_create_class(student_client) -> None:
    response = student_client.post(
        "/api/v1/classes",
        json={"name": "Unauthorized", "description": ""},
        headers={"Origin": "http://testserver"},
    )
    assert response.status_code == 403
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```powershell
cd backend
python -m pytest tests/api/test_classes.py -v
```

Expected: missing route failures.

- [ ] **Step 3: Implement classroom models, role dependency, service, and endpoints**

Create `Classroom` and `ClassMembership` with:

- `classrooms.id`, `name`, `description`, `owner_teacher_id`, `status`, `created_at`, `version`.
- `class_memberships.id`, `class_id`, `user_id`, `member_role`, `status`, `joined_at`, unique `(class_id, user_id)`.
- Owner relationship to `users.id`; membership relationships to classrooms and users.

Add a role dependency:

```python
def require_roles(*roles: str):
    def dependency(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN"})
        return user
    return dependency
```

Implement `ClassroomService.create_class` and `list_for_user`:

- Admin lists no private class data by default.
- Teacher lists only `owner_teacher_id == user.id`.
- Student lists only classes where an active membership exists.
- `POST /api/v1/classes` requires teacher role.
- `GET /api/v1/classes` returns role-filtered records.
- `GET /api/v1/classes/{class_id}` requires teacher ownership or student membership.
- `PATCH /api/v1/classes/{class_id}` accepts `{"status": "archived"}` only for the owner teacher.

- [ ] **Step 4: Run classroom tests**

Run:

```powershell
cd backend
python -m pytest tests/api/test_classes.py -v
```

Expected: all classroom tests pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/db/models/classroom.py backend/app/schemas/classroom.py backend/app/services/classrooms backend/app/api/v1/classes.py backend/app/api/v1/router.py backend/tests/api/test_classes.py
git commit -m "feat: add classrooms and role-filtered membership"
```

---

### Task 9: Add Invite Creation, Join, and Revocation

**Files:**
- Modify: `backend/app/db/models/classroom.py`
- Modify: `backend/app/schemas/classroom.py`
- Create: `backend/app/services/classrooms/invites.py`
- Modify: `backend/app/api/v1/classes.py`
- Modify: `backend/tests/api/test_classes.py`

**Interfaces:**
- Consumes: classroom ownership and student role.
- Produces: `InviteService.create`, `.join`, `.revoke`, `.validate`.
- Produces APIs: `POST /classes/{class_id}/invites`, `POST /class-invites/{code}/join`, `POST /classes/{class_id}/invites/{invite_id}/revoke`.

- [ ] **Step 1: Write failing invite tests**

```python
def test_student_joins_class_with_valid_invite(teacher_client, student_client) -> None:
    class_id = teacher_client.post(
        "/api/v1/classes",
        json={"name": "Data Structures", "description": "Fall"},
        headers={"Origin": "http://testserver"},
    ).json()["id"]
    invite = teacher_client.post(
        f"/api/v1/classes/{class_id}/invites",
        json={"expires_in_hours": 24, "max_uses": 10},
        headers={"Origin": "http://testserver"},
    )
    code = invite.json()["code"]
    joined = student_client.post(
        f"/api/v1/class-invites/{code}/join",
        headers={"Origin": "http://testserver"},
    )
    assert joined.status_code == 200
    assert joined.json()["class_id"] == class_id


def test_expired_or_revoked_invite_is_rejected(
    teacher_client, student_client, expired_invite
) -> None:
    response = student_client.post(
        f"/api/v1/class-invites/{expired_invite}/join",
        headers={"Origin": "http://testserver"},
    )
    assert response.status_code == 410
    assert response.json()["detail"]["code"] == "INVITE_INVALID"
```

- [ ] **Step 2: Run the invite tests and verify they fail**

Run:

```powershell
cd backend
python -m pytest tests/api/test_classes.py -k invite -v
```

Expected: missing invite routes.

- [ ] **Step 3: Implement secure invite handling**

- Store only SHA-256 hashes of invite codes.
- Generate codes with `secrets.token_urlsafe(18)`.
- Enforce `expires_at`, `max_uses`, `used_count`, and `status`.
- Return raw code only in the create response.
- Ensure joining uses a transaction and increments `used_count` exactly once.
- Reject archived classrooms and non-student roles.
- Repeat joins return the existing active membership without creating duplicates.
- Owner teacher can revoke unused invites.
- Emit `invite_created`, `invite_joined`, `invite_rejected`, and `invite_revoked` audit events.

- [ ] **Step 4: Run all classroom tests**

Run:

```powershell
cd backend
python -m pytest tests/api/test_classes.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/db/models/classroom.py backend/app/schemas/classroom.py backend/app/services/classrooms/invites.py backend/app/api/v1/classes.py backend/tests/api/test_classes.py
git commit -m "feat: add classroom invite lifecycle"
```

---

### Task 10: Enforce Object-Level Isolation Across Teachers and Students

**Files:**
- Create: `backend/app/services/auth/authorization.py`
- Modify: `backend/app/api/v1/classes.py`
- Modify: `backend/app/api/deps.py`
- Create: `backend/tests/integration/test_data_isolation.py`

**Interfaces:**
- Consumes: authenticated user, class, membership.
- Produces: `AuthorizationService.require_class_access(user, class_id, db) -> Classroom`; `AuthorizationService.require_teacher_owner(user, classroom) -> None`; `AuthorizationService.require_student_member(user, class_id, db) -> ClassMembership`.

- [ ] **Step 1: Write failing isolation tests**

```python
def test_other_teacher_cannot_read_class(
    teacher_client, second_teacher_client, teacher_class
) -> None:
    response = second_teacher_client.get(f"/api/v1/classes/{teacher_class.id}")
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "FORBIDDEN"


def test_nonmember_student_cannot_read_class(
    teacher_class, second_student_client
) -> None:
    response = second_student_client.get(f"/api/v1/classes/{teacher_class.id}")
    assert response.status_code == 404
    assert "owner_teacher_id" not in response.text
```

- [ ] **Step 2: Run the isolation tests and verify they fail**

Run:

```powershell
cd backend
python -m pytest tests/integration/test_data_isolation.py -v
```

Expected: at least one cross-class request succeeds or returns an incorrect status.

- [ ] **Step 3: Implement centralized authorization**

```python
# backend/app/services/auth/authorization.py
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.classroom import ClassMembership, Classroom
from app.db.models.user import Role, User


class AuthorizationService:
    def require_teacher_owner(self, user: User, classroom: Classroom) -> None:
        if user.role != Role.TEACHER.value or classroom.owner_teacher_id != user.id:
            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN"})

    def require_class_access(self, user: User, class_id: str, session: Session) -> Classroom:
        classroom = session.get(Classroom, class_id)
        if classroom is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND"})
        if user.role == Role.TEACHER.value:
            self.require_teacher_owner(user, classroom)
            return classroom
        if user.role == Role.STUDENT.value:
            membership = session.scalar(
                select(ClassMembership).where(
                    ClassMembership.class_id == class_id,
                    ClassMembership.user_id == user.id,
                    ClassMembership.status == "active",
                )
            )
            if membership is not None:
                return classroom
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND"})
```

Apply this service to every class-detail and membership endpoint. For teacher-only operations, use the teacher-owner path and return 403. For student access to an unknown or unauthorized class, return 404 to avoid leaking existence.

- [ ] **Step 4: Run all foundation tests**

Run:

```powershell
cd backend
python -m pytest tests -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/auth/authorization.py backend/app/api/v1/classes.py backend/app/api/deps.py backend/tests/integration/test_data_isolation.py
git commit -m "feat: enforce classroom data isolation"
```

---

### Task 11: Add Alembic Migration and Foundation Smoke Test

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/migrations/env.py`
- Create: `backend/migrations/script.py.mako`
- Create: `backend/migrations/versions/0001_platform_foundation.py`
- Create: `backend/tests/integration/test_foundation_migration.py`

**Interfaces:**
- Consumes: SQLAlchemy metadata for users, sessions, audit logs, classrooms, memberships, invites.
- Produces: a fresh SQLite database that can be migrated with `alembic upgrade head`.

- [ ] **Step 1: Write the failing migration test**

```python
from pathlib import Path
from sqlalchemy import create_engine, inspect


def test_migrated_database_has_platform_tables(migrated_database_url: str) -> None:
    engine = create_engine(migrated_database_url)
    tables = set(inspect(engine).get_table_names())
    assert {
        "users",
        "sessions",
        "audit_logs",
        "classrooms",
        "class_memberships",
        "class_invites",
    }.issubset(tables)
```

Use a fixture that invokes Alembic with a temporary SQLite URL and `command.upgrade(config, "head")`.

- [ ] **Step 2: Run the migration test and verify it fails**

Run:

```powershell
cd backend
python -m pytest tests/integration/test_foundation_migration.py -v
```

Expected: missing Alembic configuration or missing table.

- [ ] **Step 3: Create the initial migration**

Configure Alembic to use `Settings.database_url` and `Base.metadata`. Create revision `0001_platform_foundation` with explicit `op.create_table` calls for:

- `users`
- `sessions`
- `audit_logs`
- `classrooms`
- `class_memberships`
- `class_invites`

Add all foreign keys and unique constraints:

- `users.username`
- `sessions.token_hash`
- `(class_memberships.class_id, class_memberships.user_id)`
- `class_invites.code_hash`

Do not use `Base.metadata.create_all` as the production migration.

- [ ] **Step 4: Run the migration and the full suite**

Run:

```powershell
cd backend
alembic upgrade head
python -m pytest tests -v
```

Expected: migration succeeds and all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/alembic.ini backend/migrations backend/tests/integration/test_foundation_migration.py
git commit -m "feat: add platform foundation migrations"
```

---

## Requirement Coverage for This Plan

| Requirement | Covered by |
| --- | --- |
| FR-032 Login and session | Tasks 5, 6, 7 |
| FR-033 School account management foundation | Tasks 3, 4, 7 |
| FR-034 Classroom management foundation | Task 8 |
| FR-035 Classroom invitations | Task 9 |
| FR-041 Authorization and audit | Tasks 6, 7, 10 |
| AT-017 Multi-teacher multi-class and invite | Tasks 8, 9, 10 |
| AT-020 Cross-class data isolation | Task 10 |
| AT-028 Session disable/password reset compatibility | Tasks 5, 6 and later admin account task |

Account disable/password reset endpoints are intentionally left to the Teacher and Resource Platform plan because they are only useful once all user-linked data is present. The session schema and authentication dependency in this plan are designed so disabling a user immediately invalidates access.

## Self-Review Checklist

- [ ] The first failing test precedes each production-code step.
- [ ] Every protected endpoint uses `current_user`.
- [ ] Teacher-owned classroom checks exist in the service layer.
- [ ] Student unauthorized class access returns 404 without leaking class metadata.
- [ ] Raw session and invite tokens are never stored.
- [ ] Passwords and API keys never appear in audit payloads.
- [ ] The initial migration creates all foundation tables and unique constraints.
- [ ] `python -m pytest tests -v` passes before marking this plan complete.
- [ ] Any unexecuted task remains unchecked and is reported as unverified.
