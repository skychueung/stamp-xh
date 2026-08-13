"""Authentication integration tests for default-active registration.

All credentials in this module belong to disposable test users. Tests never
read, embed, or modify a real account password.
"""

from __future__ import annotations

import os
import uuid

# Use relaxed rate limits during tests so TestClient requests do not trip them.
os.environ.setdefault("STAMP_LOGIN_RATE_LIMIT", "100/minute")
os.environ.setdefault("STAMP_REGISTER_RATE_LIMIT", "100/hour")
os.environ.setdefault("STAMP_LOGOUT_RATE_LIMIT", "100/minute")
os.environ.setdefault("STAMP_CHANGE_PASSWORD_RATE_LIMIT", "100/minute")

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models.user import User


TEST_USER_PREFIX = "p33vt_"
TEST_ONLY_PASSWORD = "TestOnlyPass123!"


def _cleanup_test_users() -> None:
    with SessionLocal() as db:
        db.query(User).filter(User.username.like(f"{TEST_USER_PREFIX}%")).delete(
            synchronize_session=False,
        )
        db.commit()


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    Base.metadata.create_all(bind=engine)
    _cleanup_test_users()
    yield
    _cleanup_test_users()


@pytest.fixture(autouse=True)
def default_approval_mode(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STAMP_REQUIRE_ADMIN_APPROVAL", "false")


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def _unique(name: str) -> str:
    return f"{TEST_USER_PREFIX}{name}_{uuid.uuid4().hex[:8]}"


def _csrf(client: TestClient) -> str:
    return client.cookies.get("stamp_csrf", "")


def _create_user(*, username: str, status: str = "active", role: str = "user") -> User:
    with SessionLocal() as db:
        user = User(
            username=username,
            email=None,
            password_hash=hash_password(TEST_ONLY_PASSWORD),
            role=role,
            status=status,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        db.expunge(user)
        return user


def test_new_registration_is_active_and_can_login(client: TestClient):
    username = _unique("register_active")
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "password": TEST_ONLY_PASSWORD,
            "email": f"{username}@example.com",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["data"]["status"] == "active"
    assert response.json()["data"]["approval_required"] is False

    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": TEST_ONLY_PASSWORD},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "active"


def test_approval_mode_is_explicit_opt_in(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STAMP_REQUIRE_ADMIN_APPROVAL", "true")
    username = _unique("approval_opt_in")

    response = client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": TEST_ONLY_PASSWORD},
    )
    assert response.status_code == 201
    assert response.json()["data"]["status"] == "pending"
    assert response.json()["data"]["approval_required"] is True

    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": TEST_ONLY_PASSWORD},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Account is waiting for administrator approval."


def test_legacy_pending_user_is_activated_on_login(client: TestClient):
    username = _unique("legacy_pending")
    _create_user(username=username, status="pending")

    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": TEST_ONLY_PASSWORD},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "active"

    with SessionLocal() as db:
        assert db.query(User).filter(User.username == username).one().status == "active"


def test_active_user_can_login(client: TestClient):
    username = _unique("active")
    _create_user(username=username)

    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": TEST_ONLY_PASSWORD},
    )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "active"


def test_explicitly_disabled_user_is_rejected(client: TestClient):
    username = _unique("disabled")
    _create_user(username=username, status="disabled")

    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": TEST_ONLY_PASSWORD},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Account has been disabled. Please contact an administrator."


def test_wrong_password_uses_unified_message(client: TestClient):
    username = _unique("wrong_password")
    _create_user(username=username)

    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "WrongTestPassword!"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password."


def test_admin_can_approve_user_in_opt_in_mode(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("STAMP_REQUIRE_ADMIN_APPROVAL", "true")
    admin_username = _unique("admin")
    _create_user(username=admin_username, role="admin")
    username = _unique("approve")

    response = client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": TEST_ONLY_PASSWORD},
    )
    assert response.status_code == 201
    assert response.json()["data"]["status"] == "pending"

    response = client.post(
        "/api/v1/auth/login",
        json={"username": admin_username, "password": TEST_ONLY_PASSWORD},
    )
    assert response.status_code == 200
    assert response.json()["data"]["role"] == "admin"

    response = client.get("/api/v1/admin/users?status_filter=pending")
    assert response.status_code == 200
    pending = [item for item in response.json()["data"]["items"] if item["username"] == username]
    assert len(pending) == 1

    response = client.post(
        f"/api/v1/admin/users/{pending[0]['id']}/approve",
        headers={"X-CSRF-Token": _csrf(client)},
    )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "active"

    with TestClient(app) as user_client:
        response = user_client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": TEST_ONLY_PASSWORD},
        )
        assert response.status_code == 200


def test_normal_user_cannot_access_admin(client: TestClient):
    username = _unique("normal")
    _create_user(username=username)

    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": TEST_ONLY_PASSWORD},
    )
    assert response.status_code == 200
    assert client.get("/api/v1/admin/users").status_code == 403


def test_csrf_required_for_logout(client: TestClient):
    username = _unique("csrf")
    _create_user(username=username)
    assert client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": TEST_ONLY_PASSWORD},
    ).status_code == 200
    assert client.post("/api/v1/auth/logout").status_code == 403


def test_sql_injection_username_rejected(client: TestClient):
    response = client.post(
        "/api/v1/auth/register",
        json={"username": "admin' OR '1'='1", "password": TEST_ONLY_PASSWORD},
    )
    assert response.status_code == 422


def test_path_traversal_artifact_rejected(client: TestClient):
    username = _unique("path")
    _create_user(username=username)
    assert client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": TEST_ONLY_PASSWORD},
    ).status_code == 200
    response = client.get("/api/v1/target-design/results/foo/downloads/../../../etc/passwd")
    assert response.status_code in (400, 403, 404)


def test_unauthenticated_api_returns_401(client: TestClient):
    assert client.get("/api/v1/target-design/results").status_code == 401
    assert client.get("/api/v1/auth/me").status_code == 401
