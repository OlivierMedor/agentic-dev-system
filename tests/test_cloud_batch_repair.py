from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest
import yaml

from agentic_dev.cloud_application import ApplicationService
from agentic_dev.cloud_batch import build_default_batch_service
from agentic_dev.cloud_batch.audit import load_batch_audit_events
from agentic_dev.cloud_batch.graph import batch_dependency_ready_set, batch_dependency_topological_order
from agentic_dev.cloud_batch.models import (
    BATCH_SCHEMA_VERSION,
    BATCH_TYPE_CLOUD_QUEUE_ORCHESTRATION,
    BatchDependencyGraph,
    BatchItem,
    BatchRecord,
    BatchResult,
    ExecutionPolicy,
    ProgressSummary,
)
from agentic_dev.cloud_batch.persistence import load_batch_record, save_batch_record
from agentic_dev.cloud_queue import create_cloud_queue_request, export_cloud_queue_request, import_cloud_queue_response, show_cloud_queue_request
from agentic_dev.cloud_queue.persistence import checksum_text, now_iso


STORY = "story_065_parallel_cloud_batch_orchestration"


def create_story(project_path: Path) -> None:
    story_path = project_path / "stories" / STORY
    story_path.mkdir(parents=True, exist_ok=True)
    (story_path / "story.md").write_text("# STORY-065\n", encoding="utf-8")


def response_payload(request_id: str, batch_id: str, checksum: str, decision: str = "SAFE") -> dict[str, object]:
    return {
        "response_id": f"{request_id}-response",
        "request_id": request_id,
        "batch_id": batch_id,
        "response_schema_version": 1,
        "normalized_response": {"summary": checksum},
        "raw_response": checksum,
        "checksum": checksum,
        "decision": decision,
        "claims": {
            "applicable_requirements": ["AC-001"],
            "writable_paths": ["src/agentic_dev/cli.py"],
            "scope_changes": [],
            "dependency_status": "resolved",
            "resolved_dependencies": [],
            "safe_to_apply": True,
            "operation_type": "update_task_metadata",
            "task_metadata": {
                "title": "Updated task",
                "role": "developer",
                "required_context": ["story.md"],
                "writable_paths": ["src/agentic_dev/cli.py"],
                "expected_outputs": ["reports/item.md"],
                "validation_steps": ["pytest -q"],
                "token_estimate": 1000,
                "usable_input_tokens": 2000,
            },
        },
        "adapter": "manual_packet",
    }


def prepare_imported_request(tmp_path: Path, request, checksum: str) -> object:
    export_cloud_queue_request(tmp_path, request_id=request.request.request_id)
    response_path = tmp_path / f"{request.request.request_id}.response.yaml"
    response_path.write_text(
        yaml.safe_dump(response_payload(request.request.request_id, request.request.batch_id, checksum), sort_keys=False),
        encoding="utf-8",
    )
    import_cloud_queue_response(tmp_path, response_path)
    return SimpleNamespace(request=show_cloud_queue_request(tmp_path, request.request.request_id).request)


def fake_runtime(revision_id: str = "runtime-r1") -> SimpleNamespace:
    return SimpleNamespace(revision=SimpleNamespace(revision_id=revision_id, revision_checksum=f"{revision_id}-checksum"))


def fake_application_result(request_id: str, revision_id: str, *, outcome: str = "applied") -> SimpleNamespace:
    application_path = Path(f"/tmp/{request_id}.application.yaml")
    plan_path = Path(f"/tmp/{request_id}.plan.yaml")
    application = SimpleNamespace(
        application_id=f"app-{request_id}",
        request_id=request_id,
        request_checksum=f"request-{request_id}",
        response_checksum=f"response-{request_id}",
        approval_checksum="",
        revision_id=revision_id,
        status=outcome,
        application_path=application_path,
        plan_path=plan_path,
    )
    plan = SimpleNamespace(plan_checksum=f"plan-{request_id}", proposed_revision_id=revision_id)
    return SimpleNamespace(application=application, plan=plan, application_path=application_path, plan_path=plan_path)


def snapshot_paths(project_path: Path) -> dict[str, str]:
    roots = [
        project_path / ".agentic" / "cloud_queue",
        project_path / ".agentic" / "cloud_applications",
        project_path / ".agentic" / "cloud_batches",
        project_path / ".agentic" / "runtime_plans",
    ]
    snapshot: dict[str, str] = {}
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            rel_path = str(path.relative_to(project_path))
            if path.is_dir():
                snapshot[f"{rel_path}/"] = "DIR"
            else:
                snapshot[rel_path] = sha256(path.read_bytes()).hexdigest()
    return snapshot


def prepare_single_item_batch(tmp_path: Path, batch_id: str, request_id: str) -> None:
    service = build_default_batch_service(tmp_path)
    service.export(request_ids=[request_id], batch_id=batch_id)


def seed_batch_record(project_path: Path, batch_id: str, requests: list[object]) -> BatchRecord:
    items = tuple(
        BatchItem(
            item_id=request.request.request_id,
            request_id=request.request.request_id,
            status="exported",
            dependencies=tuple(request.request.dependencies),
            writable_paths=tuple(request.request.writable_paths),
            request_checksum=request.request.packet_checksum,
        )
        for request in requests
    )
    checksum = checksum_text(str([item.to_dict() for item in items]))
    dependency_graph = BatchDependencyGraph(
        schema_version=BATCH_SCHEMA_VERSION,
        batch_id=batch_id,
        node_ids=tuple(item.item_id for item in items),
        dependency_map={item.item_id: item.dependencies for item in items},
        topological_order=batch_dependency_topological_order(list(items)),
        ready_set=batch_dependency_ready_set(list(items)),
        checksum=checksum,
    )
    progress = ProgressSummary(total=len(items), pending=len(items), running=0, succeeded=0, failed=0, blocked=0, skipped=0, cancelled=0)
    batch = BatchRecord(
        schema_version=BATCH_SCHEMA_VERSION,
        batch_id=batch_id,
        batch_type=BATCH_TYPE_CLOUD_QUEUE_ORCHESTRATION,
        created_at=now_iso(),
        status="exported",
        item_ids=tuple(item.item_id for item in items),
        items=items,
        dependency_graph=dependency_graph,
        execution_policy=ExecutionPolicy(),
        progress=progress,
        results=BatchResult(
            batch_id=batch_id,
            status="exported",
            progress=progress,
            item_results=(),
            attempt_ids=(),
            checksum=checksum,
            details={"conflict_count": 0},
        ),
        checksums={"batch_record": checksum, "batch_manifest": checksum},
        attempts=(),
        audits=(),
        latest_plan_id="",
        latest_attempt_id="",
    )
    save_batch_record(project_path, batch)
    return batch


def update_batch_item(project_path: Path, batch_id: str, request_id: str, **changes: object) -> None:
    batch = load_batch_record(project_path, batch_id)
    updated_items = []
    for item in batch.items:
        if item.request_id == request_id:
            updated_items.append(type(item).from_dict({**item.to_dict(), **changes}))
        else:
            updated_items.append(item)
    save_batch_record(project_path, type(batch).from_dict({**batch.to_dict(), "items": [item.to_dict() for item in updated_items]}))


def test_batch_apply_dependency_order_and_independent_continuation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    create_story(tmp_path)
    request_a = create_cloud_queue_request(tmp_path, story=STORY, title="A", details="details", requirements=["AC-001"], writable_paths=["src/agentic_dev/cli.py"], request_id_factory=lambda: "CQ-REPAIR-A", batch_id_factory=lambda: "batch-source")
    request_b = create_cloud_queue_request(tmp_path, story=STORY, title="B", details="details", requirements=["AC-001"], writable_paths=["docs/cloud_batch_operator_guide.md"], dependencies=[request_a.request.request_id], request_id_factory=lambda: "CQ-REPAIR-B", batch_id_factory=lambda: "batch-source")
    request_c = create_cloud_queue_request(tmp_path, story=STORY, title="C", details="details", requirements=["AC-001"], writable_paths=["src/agentic_dev/runtime_config.py"], request_id_factory=lambda: "CQ-REPAIR-C", batch_id_factory=lambda: "batch-source")
    request_a = prepare_imported_request(tmp_path, request_a, "response-a")
    request_b = prepare_imported_request(tmp_path, request_b, "response-b")
    request_c = prepare_imported_request(tmp_path, request_c, "response-c")
    service = build_default_batch_service(tmp_path)
    seed_batch_record(tmp_path, "batch-repair-1", [request_a, request_b, request_c])
    monkeypatch.setattr("agentic_dev.cloud_application.service.load_active_runtime_state", lambda project_path: fake_runtime())
    monkeypatch.setattr(ApplicationService, "plan_apply", lambda self, request_id, dry_run=False: fake_application_result(request_id, "runtime-r1"))
    service.plan_apply("batch-repair-1")

    calls: list[str] = []

    def fake_plan_apply(self: ApplicationService, request_id: str, *, dry_run: bool = False):  # noqa: ANN001
        calls.append(request_id)
        if request_id == request_a.request.request_id and not dry_run:
            raise ValueError("boom")
        return fake_application_result(request_id, "runtime-r2" if request_id != request_a.request.request_id else "runtime-r1")

    monkeypatch.setattr("agentic_dev.cloud_batch.orchestration_runtime.load_active_runtime_state", lambda project_path: fake_runtime())
    monkeypatch.setattr(ApplicationService, "plan_apply", fake_plan_apply)

    result = service.apply("batch-repair-1")

    assert calls == [request_a.request.request_id, request_c.request.request_id]
    batch = service.show("batch-repair-1")
    statuses = {item.request_id: item.status for item in batch.items}
    assert statuses[request_a.request.request_id] == "failed"
    assert statuses[request_b.request.request_id] == "validation_partial"
    assert statuses[request_c.request.request_id] == "applied"
    assert result.status == "partially_failed"


def test_batch_apply_dry_run_makes_no_mutation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    create_story(tmp_path)
    request = create_cloud_queue_request(tmp_path, story=STORY, title="A", details="details", requirements=["AC-001"], writable_paths=["src/agentic_dev/cli.py"], request_id_factory=lambda: "CQ-REPAIR-DRY", batch_id_factory=lambda: "batch-source")
    service = build_default_batch_service(tmp_path)
    request = prepare_imported_request(tmp_path, request, "response-dry")
    seed_batch_record(tmp_path, "batch-repair-2", [request])
    monkeypatch.setattr("agentic_dev.cloud_application.service.load_active_runtime_state", lambda project_path: fake_runtime())
    monkeypatch.setattr(ApplicationService, "plan_apply", lambda self, request_id, dry_run=False: fake_application_result(request_id, "runtime-r1"))
    service.plan_apply("batch-repair-2")
    before = snapshot_paths(tmp_path)

    monkeypatch.setattr("agentic_dev.cloud_batch.orchestration_runtime.load_active_runtime_state", lambda project_path: fake_runtime())
    monkeypatch.setattr(ApplicationService, "plan_apply", lambda self, request_id, dry_run=False: fake_application_result(request_id, "runtime-r3"))

    result = service.apply("batch-repair-2", dry_run=True)
    after = snapshot_paths(tmp_path)

    assert result.dry_run is True
    assert before == after


def test_batch_apply_dry_run_rejects_stale_plan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    create_story(tmp_path)
    request = create_cloud_queue_request(tmp_path, story=STORY, title="A", details="details", requirements=["AC-001"], writable_paths=["src/agentic_dev/cli.py"], request_id_factory=lambda: "CQ-REPAIR-STALE-PLAN", batch_id_factory=lambda: "batch-source")
    request = prepare_imported_request(tmp_path, request, "checksum-1")
    service = build_default_batch_service(tmp_path)
    seed_batch_record(tmp_path, "batch-repair-stale-plan", [request])
    monkeypatch.setattr("agentic_dev.cloud_application.service.load_active_runtime_state", lambda project_path: fake_runtime())
    monkeypatch.setattr(ApplicationService, "plan_apply", lambda self, request_id, dry_run=False: fake_application_result(request_id, "runtime-r1"))
    service.plan_apply("batch-repair-stale-plan")
    batch = load_batch_record(tmp_path, "batch-repair-stale-plan")
    save_batch_record(tmp_path, type(batch).from_dict({**batch.to_dict(), "latest_plan_id": "stale-plan"}))

    monkeypatch.setattr("agentic_dev.cloud_batch.orchestration_runtime.load_active_runtime_state", lambda project_path: fake_runtime())
    monkeypatch.setattr(ApplicationService, "plan_apply", lambda self, request_id, dry_run=False: fake_application_result(request_id, "runtime-r1"))

    with pytest.raises(ValueError, match="Stale batch plan"):
        service.apply("batch-repair-stale-plan", dry_run=True)


def test_batch_apply_dry_run_rejects_active_revision_change(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    create_story(tmp_path)
    request_a = create_cloud_queue_request(tmp_path, story=STORY, title="A", details="details", requirements=["AC-001"], writable_paths=["src/agentic_dev/cli.py"], request_id_factory=lambda: "CQ-REPAIR-ACTIVE-A", batch_id_factory=lambda: "batch-source")
    request_b = create_cloud_queue_request(tmp_path, story=STORY, title="B", details="details", requirements=["AC-001"], writable_paths=["src/agentic_dev/runtime_config.py"], request_id_factory=lambda: "CQ-REPAIR-ACTIVE-B", batch_id_factory=lambda: "batch-source")
    request_a = prepare_imported_request(tmp_path, request_a, "response-active-a")
    request_b = prepare_imported_request(tmp_path, request_b, "response-active-b")
    service = build_default_batch_service(tmp_path)
    seed_batch_record(tmp_path, "batch-repair-active", [request_a, request_b])
    monkeypatch.setattr("agentic_dev.cloud_application.service.load_active_runtime_state", lambda project_path: fake_runtime())
    monkeypatch.setattr(ApplicationService, "plan_apply", lambda self, request_id, dry_run=False: fake_application_result(request_id, "runtime-r1"))
    service.plan_apply("batch-repair-active")

    revisions = [fake_runtime("runtime-r1"), fake_runtime("runtime-r1"), fake_runtime("runtime-r2")]

    def fake_active_runtime(project_path: Path) -> SimpleNamespace:
        return revisions.pop(0) if revisions else fake_runtime("runtime-r2")

    monkeypatch.setattr("agentic_dev.cloud_batch.orchestration_runtime.load_active_runtime_state", fake_active_runtime)
    monkeypatch.setattr(ApplicationService, "plan_apply", lambda self, request_id, dry_run=False: fake_application_result(request_id, "runtime-r1"))

    with pytest.raises(ValueError, match="Active runtime revision changed"):
        service.apply("batch-repair-active", dry_run=True)


def test_batch_apply_dry_run_rejects_approval_change(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    create_story(tmp_path)
    request = create_cloud_queue_request(tmp_path, story=STORY, title="A", details="details", requirements=["AC-001"], writable_paths=["src/agentic_dev/cli.py"], request_id_factory=lambda: "CQ-REPAIR-APPROVAL", batch_id_factory=lambda: "batch-source")
    request = prepare_imported_request(tmp_path, request, "response-approval")
    service = build_default_batch_service(tmp_path)
    seed_batch_record(tmp_path, "batch-repair-approval", [request])
    monkeypatch.setattr("agentic_dev.cloud_application.service.load_active_runtime_state", lambda project_path: fake_runtime())
    monkeypatch.setattr(ApplicationService, "plan_apply", lambda self, request_id, dry_run=False: fake_application_result(request_id, "runtime-r1"))
    service.plan_apply("batch-repair-approval")
    update_batch_item(tmp_path, "batch-repair-approval", request.request.request_id, approval_checksum="approval-old")
    approval_path = tmp_path / ".agentic" / "cloud_queue" / "approvals" / f"{request.request.request_id}.yaml"
    approval_path.parent.mkdir(parents=True, exist_ok=True)
    approval_path.write_text(
        yaml.safe_dump(
            {
                "request_id": request.request.request_id,
                "normalized_response_checksum": "approval-new",
                "approved": True,
                "operator_note": "changed",
                "recorded_at": now_iso(),
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("agentic_dev.cloud_batch.orchestration_runtime.load_active_runtime_state", lambda project_path: fake_runtime())
    monkeypatch.setattr(ApplicationService, "plan_apply", lambda self, request_id, dry_run=False: fake_application_result(request_id, "runtime-r1"))

    result = service.apply("batch-repair-approval", dry_run=True)
    assert result.status == "failed"
    assert result.dry_run is True
    assert result.item_results[0].outcome == "failed"


def test_batch_apply_dry_run_rejects_response_checksum_change(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    create_story(tmp_path)
    request = create_cloud_queue_request(tmp_path, story=STORY, title="A", details="details", requirements=["AC-001"], writable_paths=["src/agentic_dev/cli.py"], request_id_factory=lambda: "CQ-REPAIR-RESPONSE", batch_id_factory=lambda: "batch-source")
    request = prepare_imported_request(tmp_path, request, "response-old")
    service = build_default_batch_service(tmp_path)
    seed_batch_record(tmp_path, "batch-repair-response", [request])
    monkeypatch.setattr("agentic_dev.cloud_application.service.load_active_runtime_state", lambda project_path: fake_runtime())
    monkeypatch.setattr(ApplicationService, "plan_apply", lambda self, request_id, dry_run=False: fake_application_result(request_id, "runtime-r1"))
    service.plan_apply("batch-repair-response")
    update_batch_item(tmp_path, "batch-repair-response", request.request.request_id, response_checksum="response-expected")
    response_path = tmp_path / "response.yaml"
    response_path.write_text(yaml.safe_dump(response_payload(request.request.request_id, request.request.batch_id, "response-new"), sort_keys=False), encoding="utf-8")
    import_cloud_queue_response(tmp_path, response_path)

    monkeypatch.setattr("agentic_dev.cloud_batch.orchestration_runtime.load_active_runtime_state", lambda project_path: fake_runtime())
    monkeypatch.setattr(ApplicationService, "plan_apply", lambda self, request_id, dry_run=False: fake_application_result(request_id, "runtime-r1"))

    result = service.apply("batch-repair-response", dry_run=True)
    assert result.status == "failed"
    assert result.dry_run is True
    assert result.item_results[0].outcome == "failed"


def test_batch_apply_rejects_stale_runtime_revision(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    create_story(tmp_path)
    request_a = create_cloud_queue_request(tmp_path, story=STORY, title="A", details="details", requirements=["AC-001"], writable_paths=["src/agentic_dev/cli.py"], request_id_factory=lambda: "CQ-REPAIR-STALE-A", batch_id_factory=lambda: "batch-source")
    request_b = create_cloud_queue_request(tmp_path, story=STORY, title="B", details="details", requirements=["AC-001"], writable_paths=["src/agentic_dev/runtime_config.py"], request_id_factory=lambda: "CQ-REPAIR-STALE-B", batch_id_factory=lambda: "batch-source")
    request_a = prepare_imported_request(tmp_path, request_a, "response-stale-a")
    request_b = prepare_imported_request(tmp_path, request_b, "response-stale-b")
    service = build_default_batch_service(tmp_path)
    seed_batch_record(tmp_path, "batch-repair-3", [request_a, request_b])
    monkeypatch.setattr("agentic_dev.cloud_application.service.load_active_runtime_state", lambda project_path: fake_runtime())
    monkeypatch.setattr(ApplicationService, "plan_apply", lambda self, request_id, dry_run=False: fake_application_result(request_id, "runtime-r1"))
    service.plan_apply("batch-repair-3")

    revisions = ["runtime-r1", "runtime-r2", "runtime-r3", "runtime-r4"]

    def fake_active_runtime(project_path: Path) -> SimpleNamespace:
        revision_id = revisions.pop(0) if revisions else "runtime-r4"
        return fake_runtime(revision_id)

    monkeypatch.setattr("agentic_dev.cloud_batch.orchestration_runtime.load_active_runtime_state", fake_active_runtime)
    monkeypatch.setattr(ApplicationService, "plan_apply", lambda self, request_id, dry_run=False: fake_application_result(request_id, "runtime-r1"))

    with pytest.raises(ValueError, match="Active runtime revision changed"):
        service.apply("batch-repair-3")


def test_batch_apply_skips_cancelled_and_terminal_items(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    create_story(tmp_path)
    request_a = create_cloud_queue_request(tmp_path, story=STORY, title="A", details="details", requirements=["AC-001"], writable_paths=["src/agentic_dev/cli.py"], request_id_factory=lambda: "CQ-REPAIR-SKIP-A", batch_id_factory=lambda: "batch-source")
    _request_b = create_cloud_queue_request(tmp_path, story=STORY, title="B", details="details", requirements=["AC-001"], writable_paths=["docs/cloud_batch_operator_guide.md"], request_id_factory=lambda: "CQ-REPAIR-SKIP-B", batch_id_factory=lambda: "batch-source")
    request_a = prepare_imported_request(tmp_path, request_a, "response-skip-a")
    _request_b = prepare_imported_request(tmp_path, _request_b, "response-skip-b")
    service = build_default_batch_service(tmp_path)
    seed_batch_record(tmp_path, "batch-repair-3b", [request_a, _request_b])
    monkeypatch.setattr("agentic_dev.cloud_application.service.load_active_runtime_state", lambda project_path: fake_runtime())
    monkeypatch.setattr(ApplicationService, "plan_apply", lambda self, request_id, dry_run=False: fake_application_result(request_id, "runtime-r1"))
    service.plan_apply("batch-repair-3b")
    batch = load_batch_record(tmp_path, "batch-repair-3b")
    updated_items = []
    for item in batch.items:
        if item.request_id == request_a.request.request_id:
            updated_items.append(type(item).from_dict({**item.to_dict(), "status": "cancelled"}))
        else:
            updated_items.append(type(item).from_dict({**item.to_dict(), "status": "applied"}))
    save_batch_record(
        tmp_path,
        type(batch).from_dict({**batch.to_dict(), "status": "applied", "items": [item.to_dict() for item in updated_items]}),
    )

    calls: list[str] = []

    def fake_plan_apply(self: ApplicationService, request_id: str, *, dry_run: bool = False):  # noqa: ANN001
        calls.append(request_id)
        return fake_application_result(request_id, "runtime-r1")

    monkeypatch.setattr("agentic_dev.cloud_batch.orchestration_runtime.load_active_runtime_state", lambda project_path: fake_runtime())
    monkeypatch.setattr(ApplicationService, "plan_apply", fake_plan_apply)

    result = service.apply("batch-repair-3b")

    assert calls == []
    assert result.status == "validation_complete"


def test_batch_import_rejects_unrelated_member(tmp_path: Path) -> None:
    create_story(tmp_path)
    request_a = create_cloud_queue_request(tmp_path, story=STORY, title="A", details="details", requirements=["AC-001"], writable_paths=["src/agentic_dev/cli.py"], request_id_factory=lambda: "CQ-REPAIR-IMP-A", batch_id_factory=lambda: "batch-source")
    create_cloud_queue_request(tmp_path, story=STORY, title="B", details="details", requirements=["AC-001"], writable_paths=["docs/cloud_batch_operator_guide.md"], request_id_factory=lambda: "CQ-REPAIR-IMP-B", batch_id_factory=lambda: "batch-source")
    service = build_default_batch_service(tmp_path)
    service.export(all_ready=True, batch_id="batch-repair-4")
    bundle_path = tmp_path / "responses.zip"
    with ZipFile(bundle_path, "w") as archive:
        archive.writestr("foreign.yaml", yaml.safe_dump(response_payload("unrelated-request", "other-batch", "checksum-1"), sort_keys=False))
        archive.writestr("valid.yaml", yaml.safe_dump(response_payload(request_a.request.request_id, request_a.request.batch_id, "checksum-2"), sort_keys=False))

    result = service.import_bundle(bundle_path, batch_id="batch-repair-4")

    assert result.valid_count == 1
    assert result.invalid_count == 1
    assert result.member_errors[0].error_category == "batch_membership"


def test_batch_import_rejects_duplicate_across_bundles_and_replacement(tmp_path: Path) -> None:
    create_story(tmp_path)
    request_a = create_cloud_queue_request(tmp_path, story=STORY, title="A", details="details", requirements=["AC-001"], writable_paths=["src/agentic_dev/cli.py"], request_id_factory=lambda: "CQ-REPAIR-DUP-A", batch_id_factory=lambda: "batch-source")
    service = build_default_batch_service(tmp_path)
    service.export(all_ready=True, batch_id="batch-repair-5")
    bundle_one = tmp_path / "bundle-one.zip"
    with ZipFile(bundle_one, "w") as archive:
        archive.writestr("valid.yaml", yaml.safe_dump(response_payload(request_a.request.request_id, request_a.request.batch_id, "checksum-1"), sort_keys=False))
    bundle_two = tmp_path / "bundle-two.zip"
    with ZipFile(bundle_two, "w") as archive:
        archive.writestr("valid.yaml", yaml.safe_dump(response_payload(request_a.request.request_id, request_a.request.batch_id, "checksum-2"), sort_keys=False))

    first = service.import_bundle(bundle_one, batch_id="batch-repair-5")
    second = service.import_bundle(bundle_two, batch_id="batch-repair-5")

    assert first.valid_count == 1
    assert second.invalid_count == 1
    assert second.member_errors[0].error_category == "duplicate_or_replacement"


def test_batch_resume_partial_failure_isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    create_story(tmp_path)
    request_a = create_cloud_queue_request(tmp_path, story=STORY, title="A", details="details", requirements=["AC-001"], writable_paths=["src/agentic_dev/cli.py"], request_id_factory=lambda: "CQ-REPAIR-RES-A", batch_id_factory=lambda: "batch-source")
    request_b = create_cloud_queue_request(tmp_path, story=STORY, title="B", details="details", requirements=["AC-001"], writable_paths=["docs/cloud_batch_operator_guide.md"], dependencies=[request_a.request.request_id], request_id_factory=lambda: "CQ-REPAIR-RES-B", batch_id_factory=lambda: "batch-source")
    request_c = create_cloud_queue_request(tmp_path, story=STORY, title="C", details="details", requirements=["AC-001"], writable_paths=["src/agentic_dev/runtime_config.py"], request_id_factory=lambda: "CQ-REPAIR-RES-C", batch_id_factory=lambda: "batch-source")
    request_d = create_cloud_queue_request(tmp_path, story=STORY, title="D", details="details", requirements=["AC-001"], writable_paths=["docs/runtime_config.md"], request_id_factory=lambda: "CQ-REPAIR-RES-D", batch_id_factory=lambda: "batch-source")
    request_a = prepare_imported_request(tmp_path, request_a, "response-res-a")
    request_b = prepare_imported_request(tmp_path, request_b, "response-res-b")
    request_c = prepare_imported_request(tmp_path, request_c, "response-res-c")
    request_d = prepare_imported_request(tmp_path, request_d, "response-res-d")
    service = build_default_batch_service(tmp_path)
    seed_batch_record(
        tmp_path,
        "batch-repair-6",
        [
            request_a,
            request_b,
            request_c,
            request_d,
        ],
    )
    update_batch_item(tmp_path, "batch-repair-6", request_d.request.request_id, dependencies=(request_c.request.request_id,))
    monkeypatch.setattr("agentic_dev.cloud_application.service.load_active_runtime_state", lambda project_path: fake_runtime())
    monkeypatch.setattr(ApplicationService, "plan_apply", lambda self, request_id, dry_run=False: fake_application_result(request_id, "runtime-r1"))
    service.plan_apply("batch-repair-6")
    monkeypatch.setattr("agentic_dev.cloud_batch.orchestration_runtime.load_active_runtime_state", lambda project_path: fake_runtime())
    monkeypatch.setattr(ApplicationService, "plan_apply", lambda self, request_id, dry_run=False: fake_application_result(request_id, "runtime-r1"))
    service.apply("batch-repair-6")

    def fake_resume(self: ApplicationService, request_id: str):  # noqa: ANN001
        if request_id == request_a.request.request_id:
            raise ValueError("resume boom")
        return SimpleNamespace(status="resumed", lease_ids=(f"lease-{request_id}",))

    monkeypatch.setattr(ApplicationService, "resume", fake_resume)
    result = service.resume("batch-repair-6")

    assert result.status == "partially_resumed"
    batch = service.show("batch-repair-6")
    statuses = {item.request_id: item.status for item in batch.items}
    assert statuses[request_a.request.request_id] == "failed"
    assert statuses["CQ-REPAIR-RES-B"] == "validation_partial"
    assert statuses[request_c.request.request_id] == "resumed"
    assert statuses[request_d.request.request_id] == "resumed"
    events = load_batch_audit_events(tmp_path)
    assert any(event.get("event_type") == "batch_resume_item_failed" and event.get("details", {}).get("failed_item_id") == request_a.request.request_id for event in events)
