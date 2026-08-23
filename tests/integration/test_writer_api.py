"""Integration tests for Writer Sandbox API endpoints."""

from fastapi.testclient import TestClient

from phantom.api.app import create_app


def test_writer_api_dump_draft_export(tmp_path, monkeypatch):
    monkeypatch.setenv("PHANTOM_WRITER_HOME", str(tmp_path / "writer"))
    client = TestClient(create_app())

    workspace_response = client.post(
        "/api/writer/workspaces",
        json={"name": "API Writer Lab"},
    )
    assert workspace_response.status_code == 200
    workspace = workspace_response.json()

    dump_response = client.post(
        "/api/writer/dumps",
        json={
            "workspace_id": workspace["id"],
            "raw_markdown": "Ideia solta.\nComo virar post?\n- [ ] revisar depois",
            "tags": ["api"],
        },
    )
    assert dump_response.status_code == 200
    dump = dump_response.json()

    distill_response = client.post(
        f"/api/writer/dumps/{dump['id']}/distill",
        params={"workspace_id": workspace["id"]},
    )
    assert distill_response.status_code == 200
    assert distill_response.json()["questions"] == ["Como virar post?"]

    draft_response = client.post(
        "/api/writer/drafts",
        json={
            "workspace_id": workspace["id"],
            "title": "Post via API",
            "markdown": "# Post via API\n\nConteudo inicial.",
            "source_dump_ids": [dump["id"]],
        },
    )
    assert draft_response.status_code == 200
    draft = draft_response.json()

    review_response = client.post(
        f"/api/writer/drafts/{draft['id']}/review",
        params={"workspace_id": workspace["id"]},
    )
    assert review_response.status_code == 200
    assert review_response.json()["passed"] is True

    export_response = client.post(
        f"/api/writer/drafts/{draft['id']}/export",
        json={"workspace_id": workspace["id"]},
    )
    assert export_response.status_code == 200
    assert export_response.json()["message"] == "Draft exported to Markdown."


def test_writer_api_print_draft(tmp_path, monkeypatch):
    monkeypatch.setenv("PHANTOM_WRITER_HOME", str(tmp_path / "writer"))

    class FakeCompletedProcess:
        returncode = 0
        stderr = b""

    def fake_run(cmd, input=None, capture_output=None, timeout=None, check=None):
        return FakeCompletedProcess()

    monkeypatch.setattr("phantom.writer.print_service.subprocess.run", fake_run)

    client = TestClient(create_app())

    workspace = client.post("/api/writer/workspaces", json={"name": "Print Lab"}).json()
    draft = client.post(
        "/api/writer/drafts",
        json={
            "workspace_id": workspace["id"],
            "title": "Nota",
            "markdown": "Ligar para 11987654321 amanha.",
        },
    ).json()

    print_response = client.post(
        f"/api/writer/drafts/{draft['id']}/print",
        json={"workspace_id": workspace["id"], "printer": "hp-deskjet-3516"},
    )

    assert print_response.status_code == 200
    body = print_response.json()
    assert body["printer"] == "hp-deskjet-3516"
    assert body["pseudonym_count"] >= 1


def test_writer_api_ats_score(tmp_path, monkeypatch):
    monkeypatch.setenv("PHANTOM_WRITER_HOME", str(tmp_path / "writer"))
    client = TestClient(create_app())

    workspace = client.post("/api/writer/workspaces", json={"name": "Job Search"}).json()
    draft = client.post(
        "/api/writer/drafts",
        json={
            "workspace_id": workspace["id"],
            "title": "Resume",
            "markdown": "# Jane Doe\n\njane@example.com\n\n## Skills\n\n- Python\n- Docker\n",
        },
    ).json()

    response = client.post(
        f"/api/writer/drafts/{draft['id']}/ats-score",
        json={
            "workspace_id": workspace["id"],
            "job_description": "Looking for a Python engineer with Docker and Kubernetes.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert "Python" in body["keywords_found"]
    assert "Kubernetes" in body["keywords_missing"]
