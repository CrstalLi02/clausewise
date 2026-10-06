from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()["data"]["token"]


def test_user_memory_api_ownership_and_sensitive_rejection():
    with TestClient(app) as client:
        token = _login(client, "student", "student123")
        headers = {"Authorization": f"Bearer {token}"}
        created = client.post(
            "/api/v1/memory/me", headers=headers,
            json={"key": "answer_style", "value": "concise", "category": "preference", "consent": True},
        )
        assert created.status_code == 200
        memory_id = created.json()["data"]["_id"]
        rows = client.get("/api/v1/memory/me", headers=headers).json()["data"]
        assert any(row["_id"] == memory_id for row in rows)
        rejected = client.post(
            "/api/v1/memory/me", headers=headers,
            json={"key": "id number", "value": "123456", "consent": True},
        )
        assert rejected.status_code == 400
        assert client.delete(f"/api/v1/memory/me/{memory_id}", headers=headers).status_code == 200
        assert client.get("/api/v1/memory/me", headers=headers).json()["data"] == []


def test_student_cannot_publish_organization_memory():
    with TestClient(app) as client:
        token = _login(client, "student", "student123")
        response = client.post(
            "/api/v1/memory/organization",
            headers={"Authorization": f"Bearer {token}"},
            json={"scope": "department", "dept_id": "dept_jwc", "title": "FAQ", "content": "content"},
        )
        assert response.status_code == 403


def test_admin_system_insights_and_department_scope():
    with TestClient(app) as client:
        admin = _login(client, "admin", "admin123")
        dept_admin = _login(client, "jwc_admin", "admin123")

        insights = client.get(
            "/api/v1/admin/system-insights",
            headers={"Authorization": f"Bearer {admin}"},
        )
        assert insights.status_code == 200
        data = insights.json()["data"]
        assert len(data["memory_planes"]) == 5
        assert "fact_plane" in data and "evolution" in data and "signals" in data

        forbidden = client.post(
            "/api/v1/admin/loop/run",
            headers={"Authorization": f"Bearer {dept_admin}"},
        )
        assert forbidden.status_code == 403
        assert client.get(
            "/api/v1/admin/loop/jobs",
            headers={"Authorization": f"Bearer {dept_admin}"},
        ).status_code == 403
