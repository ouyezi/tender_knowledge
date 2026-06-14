from uuid import uuid4

from src.models.generation_task import GenerationTask, GenerationTaskStatus


def test_create_generation_task(db_session, seeded_kb):
    task = GenerationTask(
        kb_id=seeded_kb.kb_id,
        requirement_context_id=uuid4(),
        target_outline_node={"title": "1.1 总体架构", "level": 2, "sort_order": 1},
        status=GenerationTaskStatus.pending,
        request_snapshot={"variable_values": {}},
        created_by="tester",
    )
    db_session.add(task)
    db_session.commit()
    assert task.task_id is not None
