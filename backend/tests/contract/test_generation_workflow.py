from tests.contract.test_generation_snapshots import _complete_generation_draft


def test_accept_then_regenerate_creates_new_task(
    client, db_session, epic6_generation_seed, monkeypatch
):
    completed = _complete_generation_draft(client, db_session, epic6_generation_seed, monkeypatch)
    draft_id = completed["draft_id"]

    accept = client.post(
        f"/api/v1/kbs/{completed['kb_id']}/generation/drafts/{draft_id}/accept",
        headers={"X-Operator-Id": "tester"},
    )
    assert accept.status_code == 200
    assert accept.json()["data"]["outcome_status"] == "accepted"

    regen = client.post(
        f"/api/v1/kbs/{completed['kb_id']}/generation/drafts/{draft_id}/regenerate",
        json={"variable_values": {"project_name": "v2"}},
        headers={"X-Operator-Id": "tester"},
    )
    assert regen.status_code in (200, 202)
    assert regen.json()["data"]["task_id"] != completed["task_id"]
