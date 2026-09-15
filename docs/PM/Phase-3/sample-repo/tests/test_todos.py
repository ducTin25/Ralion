from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db() -> Generator:
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def _reset_db() -> Generator[None, None, None]:
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


client = TestClient(app)


def test_create_todo() -> None:
    response = client.post("/todos", json={"title": "Viết báo cáo", "priority": "high"})
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Viết báo cáo"
    assert body["priority"] == "high"
    assert body["is_done"] is False


def test_list_todos_filters_by_is_done() -> None:
    client.post("/todos", json={"title": "A"})
    done_id = client.post("/todos", json={"title": "B"}).json()["id"]
    client.patch(f"/todos/{done_id}", json={"is_done": True})

    response = client.get("/todos", params={"is_done": True})
    assert response.status_code == 200
    titles = [t["title"] for t in response.json()]
    assert titles == ["B"]


def test_get_todo_not_found_returns_404() -> None:
    response = client.get("/todos/999")
    assert response.status_code == 404


def test_update_todo_partial_fields_only() -> None:
    todo_id = client.post("/todos", json={"title": "Old title", "priority": "low"}).json()["id"]
    response = client.patch(f"/todos/{todo_id}", json={"is_done": True})
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Old title"
    assert body["priority"] == "low"
    assert body["is_done"] is True


def test_delete_todo() -> None:
    todo_id = client.post("/todos", json={"title": "Xoá tôi đi"}).json()["id"]
    delete_response = client.delete(f"/todos/{todo_id}")
    assert delete_response.status_code == 204
    get_response = client.get(f"/todos/{todo_id}")
    assert get_response.status_code == 404
