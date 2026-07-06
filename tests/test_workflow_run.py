from pathlib import Path
from typing import Any

import pytest
import yaml

from agentic_dev.cli import main
from agentic_dev.workflow_run import (
    CLOUD_REVIEW_PREP_PHASE,
    LOCAL_FINALIZE_PHASE,
    PREPARE_PHASE,
    WORKFLOW_RUN_NODES,
    SafeStep,
    SafeStepResult,
    build_safe_steps,
    build_workflow_run_graph,
    run_workflow_run,
)
from agentic_dev.test_layers import TEST_LAYER_PASSED


STORY = "story_028_langgraph_safe_workflow_runner"
LOCAL_FINALIZE_STEPS = [
    "test-layers",
    "finalize-story",
    "review-bundle",
    "workflow-preview",
]
PREPARE_STEPS = [
    "prepare-story",
    "micro-readiness",
    "workflow-preview",
]
CLOUD_REVIEW_PREP_STEPS = [
    "cloud-review-packet",
    "workflow-preview",
]


@pytest.fixture(autouse=True)
def mock_validate_review_bundle(monkeypatch: pytest.MonkeyPatch) -> None:
    from agentic_dev.review_state.service import ReviewBundleValidation
    monkeypatch.setattr(
        "agentic_dev.cloud_review_packet.validate_review_bundle",
        lambda *args, **kwargs: ReviewBundleValidation(True, [], None, Path(), Path())
    )


def create_story(project_path: Path, story: str = STORY) -> Path:
    story_path = project_path / "stories" / story
    story_path.mkdir(parents=True, exist_ok=True)
    (story_path / "story.md").write_text(f"# {story}\n\nstory_id: {story}\n\n## Acceptance Criteria\n\n- valid criteria\n", encoding="utf-8")
    (story_path / "status.yaml").write_text(
        f"story_id: {story}\n"
        "status: in_progress\n"
        "ready_for_review: false\n",
        encoding="utf-8",
    )
    
    blueprints_path = project_path / "blueprints"
    blueprints_path.mkdir(exist_ok=True)
    bp_file = blueprints_path / "blueprint.yaml"
    if not bp_file.exists():
        bp_file.write_text("stories:\n  - slug: " + story + "\n    story_id: " + story + "\n    title: " + story + "\n", encoding="utf-8")
    else:
        bp = bp_file.read_text(encoding="utf-8")
        if story not in bp:
            bp_file.write_text(bp + "  - slug: " + story + "\n    story_id: " + story + "\n    title: " + story + "\n", encoding="utf-8")
            
    return story_path


def write_runtime_config(project_path: Path, default_base_ref: str) -> Path:
    config_path = project_path / ".agentic" / "agent_runtime.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(f"default_base_ref: {default_base_ref}\n", encoding="utf-8")
    return config_path


def read_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def write_finalize_result(story_path: Path, ready_for_review: bool) -> None:
    reports_path = story_path / "reports"
    reports_path.mkdir(exist_ok=True)
    (reports_path / "finalize_story_result.yaml").write_text(
        yaml.safe_dump(
            {
                "status": "ready_for_review" if ready_for_review else "REQUEST_CHANGES",
                "ready_for_review": ready_for_review,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def fake_step_runner(calls: list[str]):
    def run_step(project_path: Path, story: str, step: SafeStep) -> SafeStepResult:
        calls.append(step.name)
        reports_path = project_path / "stories" / story / "reports"
        result_path = reports_path / f"{step.name.replace('-', '_')}_fake_result.yaml"
        report_path = reports_path / f"{step.name.replace('-', '_')}_fake_report.md"
        result_path.write_text("status: PASSED\n", encoding="utf-8")
        report_path.write_text(f"# {step.name}\n", encoding="utf-8")
        return SafeStepResult(
            step=step.name,
            command=" ".join(step.command),
            ran=True,
            status="PASSED",
            returncode=0,
            summary=f"{step.name} passed under fake execution.",
            result_path=result_path,
            report_path=report_path,
        )

    return run_step


def assert_workflow_run_safety_flags(result_data: dict[str, Any]) -> None:
    assert result_data["executed_agents"] is False
    assert result_data["called_cloud_models"] is False
    assert result_data["called_github_apis"] is False
    assert result_data["committed_or_merged"] is False
    assert result_data["pushed"] is False
    assert result_data["merged"] is False
    assert result_data["deployed"] is False
    assert result_data["ran_destructive_commands"] is False
    assert result_data["ran_arbitrary_commands"] is False


def test_build_workflow_run_graph_contains_expected_nodes() -> None:
    graph = build_workflow_run_graph()

    assert callable(graph.invoke)
    assert set(WORKFLOW_RUN_NODES).issubset(set(graph.get_graph().nodes))


def test_workflow_run_validates_story_folder_exists(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Story folder does not exist") as error:
        run_workflow_run(tmp_path, STORY)

    assert STORY in str(error.value)


def test_workflow_run_supports_local_finalize_phase_and_rejects_unsupported_phase(
    tmp_path: Path,
) -> None:
    create_story(tmp_path)

    result = run_workflow_run(tmp_path, STORY, phase=LOCAL_FINALIZE_PHASE)
    prepare_result = run_workflow_run(tmp_path, STORY, phase=PREPARE_PHASE)
    cloud_review_prep_result = run_workflow_run(
        tmp_path,
        STORY,
        phase=CLOUD_REVIEW_PREP_PHASE,
    )

    assert result.phase == LOCAL_FINALIZE_PHASE
    assert prepare_result.phase == PREPARE_PHASE
    assert cloud_review_prep_result.phase == CLOUD_REVIEW_PREP_PHASE
    with pytest.raises(ValueError, match="Unsupported workflow-run phase: deploy"):
        run_workflow_run(tmp_path, STORY, phase="deploy")


def test_workflow_run_dry_run_writes_plan_without_running_safe_steps(
    tmp_path: Path,
) -> None:
    story_path = create_story(tmp_path)
    calls: list[str] = []

    result = run_workflow_run(
        tmp_path,
        STORY,
        execute=False,
        step_runner=fake_step_runner(calls),
    )

    assert calls == []
    assert result.executed is False
    assert result.status == "planned"
    assert result.safe_steps_planned == LOCAL_FINALIZE_STEPS
    assert result.safe_steps_executed == []
    assert result.step_results == []
    assert result.graph_nodes_visited == list(WORKFLOW_RUN_NODES)
    assert result.result_path == story_path / "reports" / "workflow_run_result.yaml"
    assert result.report_path == story_path / "reports" / "workflow_run_report.md"
    assert result.result_path.exists()
    assert result.report_path.exists()

    result_data = read_yaml(result.result_path)
    report = result.report_path.read_text(encoding="utf-8")
    assert result_data["executed"] is False
    assert result_data["status"] == "planned"
    assert result_data["graph_nodes_visited"] == list(WORKFLOW_RUN_NODES)
    assert result_data["safe_steps_planned"] == LOCAL_FINALIZE_STEPS
    assert result_data["safe_steps_executed"] == []
    assert result_data["step_results"] == []
    assert_workflow_run_safety_flags(result_data)
    assert "Dry run only. No workflow steps ran" in report
    assert "No command results. Dry run mode only planned the safe steps." in report


def test_workflow_run_execute_runs_safe_local_finalize_steps_with_fake_runner(
    tmp_path: Path,
) -> None:
    create_story(tmp_path)
    calls: list[str] = []

    result = run_workflow_run(
        tmp_path,
        STORY,
        execute=True,
        step_runner=fake_step_runner(calls),
    )

    assert calls == LOCAL_FINALIZE_STEPS
    assert result.executed is True
    assert result.status == "completed"
    assert result.safe_steps_planned == LOCAL_FINALIZE_STEPS
    assert result.safe_steps_executed == LOCAL_FINALIZE_STEPS
    assert [step_result.step for step_result in result.step_results] == LOCAL_FINALIZE_STEPS
    assert all(step_result.ran for step_result in result.step_results)
    assert all(step_result.returncode == 0 for step_result in result.step_results)

    result_data = read_yaml(result.result_path)
    report = result.report_path.read_text(encoding="utf-8")
    assert result_data["executed"] is True
    assert result_data["status"] == "completed"
    assert result_data["safe_steps_executed"] == LOCAL_FINALIZE_STEPS
    assert [step_result["step"] for step_result in result_data["step_results"]] == (
        LOCAL_FINALIZE_STEPS
    )
    assert_workflow_run_safety_flags(result_data)
    assert "Execution happened because `--execute` was provided." in report
    assert "test-layers: PASSED" in report
    assert "finalize-story: PASSED" in report
    assert "review-bundle: PASSED" in report
    assert "workflow-preview: PASSED" in report


def test_workflow_run_local_finalize_uses_project_default_base_ref(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_story(tmp_path)
    default_base_ref = "origin/phase/01-funding-spike-detector"
    write_runtime_config(tmp_path, default_base_ref)
    finalize_calls: list[str | None] = []
    review_calls: list[str | None] = []

    class FakeFinalizeResult:
        ready_for_review = True
        status = "ready_for_review"
        finalize_result_path = tmp_path / "stories" / STORY / "reports" / "finalize_story_result.yaml"
        finalize_report_path = tmp_path / "stories" / STORY / "reports" / "finalize_story_report.md"

    class FakeReviewBundleResult:
        pytest_passed = True
        ruff_passed = True
        review_bundle_path = tmp_path / "stories" / STORY / "review_bundle"

    class FakeWorkflowPreviewResult:
        result_path = tmp_path / "stories" / STORY / "reports" / "workflow_preview_result.yaml"
        report_path = tmp_path / "stories" / STORY / "reports" / "workflow_preview_report.md"
        recommended_next_action = "Continue."

    class FakeTestLayerResult:
        status = TEST_LAYER_PASSED
        result_path = tmp_path / "stories" / STORY / "reports" / "test_layer_result.yaml"
        report_path = tmp_path / "stories" / STORY / "reports" / "test_layer_report.md"

    def fake_finalize_story(
        project_path: Path,
        story: str,
        force: bool = False,
        command_runner=None,
        base_ref: str | None = None,
    ) -> FakeFinalizeResult:
        finalize_calls.append(base_ref)
        assert project_path == tmp_path
        assert story == STORY
        assert base_ref == default_base_ref
        FakeFinalizeResult.finalize_result_path.parent.mkdir(parents=True, exist_ok=True)
        FakeFinalizeResult.finalize_result_path.write_text("ready_for_review: true\n", encoding="utf-8")
        FakeFinalizeResult.finalize_report_path.write_text("# finalize\n", encoding="utf-8")
        return FakeFinalizeResult()

    def fake_create_review_bundle(
        project_path: Path,
        story: str,
        base_ref: str | None = None,
        command_runner=None,
        strict_clean: bool = False,
        diagnose_git_state: bool = False,
        allow_generated_artifacts: bool = False,
        host_identity_file: Path | None = None,
    ) -> FakeReviewBundleResult:
        review_calls.append(base_ref)
        assert project_path == tmp_path
        assert story == STORY
        assert base_ref == default_base_ref
        FakeReviewBundleResult.review_bundle_path.mkdir(parents=True, exist_ok=True)
        (FakeReviewBundleResult.review_bundle_path / "handoff.md").write_text(
            "# handoff\n",
            encoding="utf-8",
        )
        return FakeReviewBundleResult()

    def fake_run_test_layers(project_path: Path, story: str) -> FakeTestLayerResult:
        assert project_path == tmp_path
        assert story == STORY
        FakeTestLayerResult.result_path.parent.mkdir(parents=True, exist_ok=True)
        FakeTestLayerResult.result_path.write_text("status: PASSED\n", encoding="utf-8")
        FakeTestLayerResult.report_path.write_text("# test layers\n", encoding="utf-8")
        return FakeTestLayerResult()

    def fake_run_workflow_preview(project_path: Path, story: str) -> FakeWorkflowPreviewResult:
        assert project_path == tmp_path
        assert story == STORY
        FakeWorkflowPreviewResult.result_path.parent.mkdir(parents=True, exist_ok=True)
        FakeWorkflowPreviewResult.result_path.write_text("status: completed\n", encoding="utf-8")
        FakeWorkflowPreviewResult.report_path.write_text("# workflow preview\n", encoding="utf-8")
        return FakeWorkflowPreviewResult()

    monkeypatch.setattr("agentic_dev.workflow_run.finalize_story", fake_finalize_story)
    monkeypatch.setattr("agentic_dev.workflow_run.create_review_bundle", fake_create_review_bundle)
    monkeypatch.setattr("agentic_dev.workflow_run.run_test_layers", fake_run_test_layers)
    monkeypatch.setattr("agentic_dev.workflow_run.run_workflow_preview", fake_run_workflow_preview)

    result = run_workflow_run(tmp_path, STORY, execute=True)
    result_data = read_yaml(result.result_path)

    assert finalize_calls == [default_base_ref]
    assert review_calls == [default_base_ref]
    assert result.status == "completed"
    assert result.safe_steps_planned == [
        "test-layers",
        "finalize-story",
        "review-bundle",
        "workflow-preview",
    ]
    assert any(default_base_ref in step_result.command for step_result in result.step_results)
    assert "finalize-story --project" in result.report_path.read_text(encoding="utf-8")
    assert result_data["status"] == "completed"


def test_workflow_run_explicit_origin_main_base_ref_overrides_project_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_story(tmp_path)
    write_runtime_config(tmp_path, "origin/phase/01-funding-spike-detector")
    seen_base_refs: list[str | None] = []

    class FakeFinalizeResult:
        ready_for_review = True
        status = "ready_for_review"
        finalize_result_path = tmp_path / "stories" / STORY / "reports" / "finalize_story_result.yaml"
        finalize_report_path = tmp_path / "stories" / STORY / "reports" / "finalize_story_report.md"

    class FakeReviewBundleResult:
        pytest_passed = True
        ruff_passed = True
        review_bundle_path = tmp_path / "stories" / STORY / "review_bundle"

    class FakeWorkflowPreviewResult:
        result_path = tmp_path / "stories" / STORY / "reports" / "workflow_preview_result.yaml"
        report_path = tmp_path / "stories" / STORY / "reports" / "workflow_preview_report.md"
        recommended_next_action = "Continue."

    class FakeTestLayerResult:
        status = TEST_LAYER_PASSED
        result_path = tmp_path / "stories" / STORY / "reports" / "test_layer_result.yaml"
        report_path = tmp_path / "stories" / STORY / "reports" / "test_layer_report.md"

    def fake_finalize_story(
        project_path: Path,
        story: str,
        force: bool = False,
        command_runner=None,
        base_ref: str | None = None,
    ) -> FakeFinalizeResult:
        seen_base_refs.append(base_ref)
        assert base_ref == "origin/main"
        FakeFinalizeResult.finalize_result_path.parent.mkdir(parents=True, exist_ok=True)
        FakeFinalizeResult.finalize_result_path.write_text("ready_for_review: true\n", encoding="utf-8")
        FakeFinalizeResult.finalize_report_path.write_text("# finalize\n", encoding="utf-8")
        return FakeFinalizeResult()

    def fake_create_review_bundle(
        project_path: Path,
        story: str,
        base_ref: str | None = None,
        command_runner=None,
        strict_clean: bool = False,
        diagnose_git_state: bool = False,
        allow_generated_artifacts: bool = False,
        host_identity_file: Path | None = None,
    ) -> FakeReviewBundleResult:
        seen_base_refs.append(base_ref)
        assert base_ref == "origin/main"
        FakeReviewBundleResult.review_bundle_path.mkdir(parents=True, exist_ok=True)
        (FakeReviewBundleResult.review_bundle_path / "handoff.md").write_text("# handoff\n", encoding="utf-8")
        return FakeReviewBundleResult()

    def fake_run_test_layers(project_path: Path, story: str) -> FakeTestLayerResult:
        FakeTestLayerResult.result_path.parent.mkdir(parents=True, exist_ok=True)
        FakeTestLayerResult.result_path.write_text("status: PASSED\n", encoding="utf-8")
        FakeTestLayerResult.report_path.write_text("# test layers\n", encoding="utf-8")
        return FakeTestLayerResult()

    def fake_run_workflow_preview(project_path: Path, story: str) -> FakeWorkflowPreviewResult:
        FakeWorkflowPreviewResult.result_path.parent.mkdir(parents=True, exist_ok=True)
        FakeWorkflowPreviewResult.result_path.write_text("status: completed\n", encoding="utf-8")
        FakeWorkflowPreviewResult.report_path.write_text("# workflow preview\n", encoding="utf-8")
        return FakeWorkflowPreviewResult()

    monkeypatch.setattr("agentic_dev.workflow_run.finalize_story", fake_finalize_story)
    monkeypatch.setattr("agentic_dev.workflow_run.create_review_bundle", fake_create_review_bundle)
    monkeypatch.setattr("agentic_dev.workflow_run.run_test_layers", fake_run_test_layers)
    monkeypatch.setattr("agentic_dev.workflow_run.run_workflow_preview", fake_run_workflow_preview)

    result = run_workflow_run(tmp_path, STORY, execute=True, base_ref="origin/main")

    assert seen_base_refs == ["origin/main", "origin/main"]
    assert result.status == "completed"


def test_workflow_run_prepare_dry_run_writes_plan_without_running_safe_steps(
    tmp_path: Path,
) -> None:
    story_path = create_story(tmp_path)
    calls: list[str] = []

    result = run_workflow_run(
        tmp_path,
        STORY,
        phase=PREPARE_PHASE,
        execute=False,
        step_runner=fake_step_runner(calls),
    )

    assert calls == []
    assert result.phase == PREPARE_PHASE
    assert result.executed is False
    assert result.status == "planned"
    assert result.safe_steps_planned == PREPARE_STEPS
    assert result.safe_steps_executed == []
    assert result.step_results == []
    assert result.graph_nodes_visited == list(WORKFLOW_RUN_NODES)
    assert result.result_path == story_path / "reports" / "workflow_run_result.yaml"
    assert result.report_path == story_path / "reports" / "workflow_run_report.md"

    result_data = read_yaml(result.result_path)
    report = result.report_path.read_text(encoding="utf-8")
    assert result_data["phase"] == PREPARE_PHASE
    assert result_data["executed"] is False
    assert result_data["status"] == "planned"
    assert result_data["graph_nodes_visited"] == list(WORKFLOW_RUN_NODES)
    assert result_data["safe_steps_planned"] == PREPARE_STEPS
    assert result_data["safe_steps_executed"] == []
    assert result_data["step_results"] == []
    assert_workflow_run_safety_flags(result_data)
    assert "Dry run only. No workflow steps ran" in report
    assert "prepare-story" in report
    assert "micro-readiness" in report
    assert "workflow-preview" in report


def test_workflow_run_prepare_execute_runs_only_safe_prepare_steps_with_fake_runner(
    tmp_path: Path,
) -> None:
    create_story(tmp_path)
    calls: list[str] = []

    result = run_workflow_run(
        tmp_path,
        STORY,
        phase=PREPARE_PHASE,
        execute=True,
        step_runner=fake_step_runner(calls),
    )

    assert calls == PREPARE_STEPS
    assert result.executed is True
    assert result.status == "completed"
    assert result.safe_steps_planned == PREPARE_STEPS
    assert result.safe_steps_executed == PREPARE_STEPS
    assert [step_result.step for step_result in result.step_results] == PREPARE_STEPS
    assert all(step_result.ran for step_result in result.step_results)

    result_data = read_yaml(result.result_path)
    report = result.report_path.read_text(encoding="utf-8")
    assert result_data["phase"] == PREPARE_PHASE
    assert result_data["executed"] is True
    assert result_data["status"] == "completed"
    assert result_data["graph_nodes_visited"] == list(WORKFLOW_RUN_NODES)
    assert result_data["safe_steps_planned"] == PREPARE_STEPS
    assert result_data["safe_steps_executed"] == PREPARE_STEPS
    assert [step_result["step"] for step_result in result_data["step_results"]] == PREPARE_STEPS
    assert_workflow_run_safety_flags(result_data)
    assert "Execution happened because `--execute` was provided." in report
    assert "prepare-story: PASSED" in report
    assert "micro-readiness: PASSED" in report
    assert "workflow-preview: PASSED" in report
    assert "generated agent prompts" in report


def test_workflow_run_prepare_records_micro_readiness_step_result(
    tmp_path: Path,
) -> None:
    create_story(tmp_path)
    calls: list[str] = []

    result = run_workflow_run(
        tmp_path,
        STORY,
        phase=PREPARE_PHASE,
        execute=True,
        step_runner=fake_step_runner(calls),
    )
    result_data = read_yaml(result.result_path)

    micro_step = next(
        step_result
        for step_result in result_data["step_results"]
        if step_result["step"] == "micro-readiness"
    )
    assert calls == PREPARE_STEPS
    assert micro_step["ran"] is True
    assert micro_step["status"] == "PASSED"
    assert "agentic micro-readiness" in micro_step["command"]


def test_workflow_run_cloud_review_prep_dry_run_writes_plan_without_running_steps(
    tmp_path: Path,
) -> None:
    story_path = create_story(tmp_path)
    calls: list[str] = []

    result = run_workflow_run(
        tmp_path,
        STORY,
        phase=CLOUD_REVIEW_PREP_PHASE,
        execute=False,
        step_runner=fake_step_runner(calls),
    )

    assert calls == []
    assert result.phase == CLOUD_REVIEW_PREP_PHASE
    assert result.executed is False
    assert result.status == "planned"
    assert result.safe_steps_planned == CLOUD_REVIEW_PREP_STEPS
    assert result.safe_steps_executed == []
    assert result.step_results == []
    assert result.graph_nodes_visited == list(WORKFLOW_RUN_NODES)
    assert result.result_path == story_path / "reports" / "workflow_run_result.yaml"
    assert result.report_path == story_path / "reports" / "workflow_run_report.md"

    result_data = read_yaml(result.result_path)
    report = result.report_path.read_text(encoding="utf-8")
    assert result_data["phase"] == CLOUD_REVIEW_PREP_PHASE
    assert result_data["executed"] is False
    assert result_data["status"] == "planned"
    assert result_data["graph_nodes_visited"] == list(WORKFLOW_RUN_NODES)
    assert result_data["safe_steps_planned"] == CLOUD_REVIEW_PREP_STEPS
    assert result_data["safe_steps_executed"] == []
    assert result_data["step_results"] == []
    assert_workflow_run_safety_flags(result_data)
    assert "Dry run only. No workflow steps ran" in report
    assert "cloud-review-packet" in report
    assert "workflow-preview" in report


def test_workflow_run_cloud_review_prep_execute_requires_finalize_result(
    tmp_path: Path,
) -> None:
    story_path = create_story(tmp_path)
    calls: list[str] = []

    result = run_workflow_run(
        tmp_path,
        STORY,
        phase=CLOUD_REVIEW_PREP_PHASE,
        execute=True,
        step_runner=fake_step_runner(calls),
    )

    assert calls == []
    assert result.executed is True
    assert result.status == "REQUEST_CHANGES"
    assert result.safe_steps_planned == CLOUD_REVIEW_PREP_STEPS
    assert result.safe_steps_executed == []
    assert [step_result.step for step_result in result.step_results] == [
        "finalize-story-readiness"
    ]
    assert result.step_results[0].ran is False
    assert result.step_results[0].status == "REQUEST_CHANGES"
    assert "finalize_story_result.yaml is missing" in result.step_results[0].summary
    assert not (story_path / "cloud_review_packet" / "cloud_review_export.md").exists()

    result_data = read_yaml(result.result_path)
    assert result_data["status"] == "REQUEST_CHANGES"
    assert result_data["safe_steps_executed"] == []
    assert result_data["step_results"][0]["step"] == "finalize-story-readiness"
    assert result_data["step_results"][0]["ran"] is False
    assert_workflow_run_safety_flags(result_data)


def test_workflow_run_cloud_review_prep_execute_requires_finalize_ready(
    tmp_path: Path,
) -> None:
    story_path = create_story(tmp_path)
    write_finalize_result(story_path, ready_for_review=False)
    calls: list[str] = []

    result = run_workflow_run(
        tmp_path,
        STORY,
        phase=CLOUD_REVIEW_PREP_PHASE,
        execute=True,
        step_runner=fake_step_runner(calls),
    )

    assert calls == []
    assert result.status == "REQUEST_CHANGES"
    assert result.safe_steps_executed == []
    assert result.step_results[0].step == "finalize-story-readiness"
    assert "not ready_for_review: true" in result.step_results[0].summary
    assert not (story_path / "cloud_review_packet" / "cloud_review_export.md").exists()

    result_data = read_yaml(result.result_path)
    assert result_data["safe_steps_planned"] == CLOUD_REVIEW_PREP_STEPS
    assert result_data["safe_steps_executed"] == []
    assert result_data["step_results"][0]["status"] == "REQUEST_CHANGES"
    assert_workflow_run_safety_flags(result_data)


def test_workflow_run_cloud_review_prep_execute_runs_safe_steps_when_finalize_ready(
    tmp_path: Path,
) -> None:
    story_path = create_story(tmp_path)
    write_finalize_result(story_path, ready_for_review=True)
    calls: list[str] = []

    result = run_workflow_run(
        tmp_path,
        STORY,
        phase=CLOUD_REVIEW_PREP_PHASE,
        execute=True,
        step_runner=fake_step_runner(calls),
    )

    assert calls == CLOUD_REVIEW_PREP_STEPS
    assert result.executed is True
    assert result.status == "completed"
    assert result.safe_steps_planned == CLOUD_REVIEW_PREP_STEPS
    assert result.safe_steps_executed == CLOUD_REVIEW_PREP_STEPS
    assert [step_result.step for step_result in result.step_results] == (
        CLOUD_REVIEW_PREP_STEPS
    )
    assert all(step_result.ran for step_result in result.step_results)

    result_data = read_yaml(result.result_path)
    report = result.report_path.read_text(encoding="utf-8")
    assert result_data["phase"] == CLOUD_REVIEW_PREP_PHASE
    assert result_data["executed"] is True
    assert result_data["status"] == "completed"
    assert result_data["graph_nodes_visited"] == list(WORKFLOW_RUN_NODES)
    assert result_data["safe_steps_planned"] == CLOUD_REVIEW_PREP_STEPS
    assert result_data["safe_steps_executed"] == CLOUD_REVIEW_PREP_STEPS
    assert [step_result["step"] for step_result in result_data["step_results"]] == (
        CLOUD_REVIEW_PREP_STEPS
    )
    assert_workflow_run_safety_flags(result_data)
    assert "cloud-review-packet: PASSED" in report
    assert "workflow-preview: PASSED" in report
    assert "did not execute agents or generated agent prompts" in report
    assert "did not call cloud models or GitHub APIs" in report


def test_workflow_run_cloud_review_prep_passes_force_to_packet_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    story_path = create_story(tmp_path)
    write_finalize_result(story_path, ready_for_review=True)
    force_values: list[bool] = []

    class FakePacketResult:
        def __init__(self) -> None:
            self.packet_path = story_path / "cloud_review_packet"
            self.generated_files = [self.packet_path / "cloud_review_prompt.md"]
            self.missing_optional_files: list[str] = []

    def fake_create_cloud_review_packet(
        project_path: Path,
        story: str,
        force: bool = False,
    ) -> FakePacketResult:
        assert project_path == tmp_path
        assert story == STORY
        force_values.append(force)
        packet_path = story_path / "cloud_review_packet"
        packet_path.mkdir(exist_ok=True)
        (packet_path / "cloud_review_export.md").write_text(
            "packet\n",
            encoding="utf-8",
        )
        return FakePacketResult()

    monkeypatch.setattr(
        "agentic_dev.workflow_run.create_cloud_review_packet",
        fake_create_cloud_review_packet,
    )

    result = run_workflow_run(
        tmp_path,
        STORY,
        phase=CLOUD_REVIEW_PREP_PHASE,
        execute=True,
    )
    result_data = read_yaml(result.result_path)

    assert force_values == [True]
    assert result.status == "completed"
    assert result_data["step_results"][0]["command"].endswith("--force")
    assert_workflow_run_safety_flags(result_data)


def test_workflow_run_cloud_review_prep_failed_step_next_action_names_step(
    tmp_path: Path,
) -> None:
    story_path = create_story(tmp_path)
    write_finalize_result(story_path, ready_for_review=True)

    def fail_cloud_review_packet(
        _project_path: Path,
        _story: str,
        step: SafeStep,
    ) -> SafeStepResult:
        if step.name == "cloud-review-packet":
            return SafeStepResult(
                step=step.name,
                command="agentic cloud-review-packet --force",
                ran=True,
                status="FAILED",
                returncode=1,
                summary="packet refresh failed",
            )
        return fake_step_runner([])(_project_path, _story, step)

    result = run_workflow_run(
        tmp_path,
        STORY,
        phase=CLOUD_REVIEW_PREP_PHASE,
        execute=True,
        step_runner=fail_cloud_review_packet,
    )
    result_data = read_yaml(result.result_path)

    assert result.status == "failed"
    assert result_data["next_action"] == (
        "Fix the failed cloud-review-prep step `cloud-review-packet`, "
        "then rerun workflow-run --phase cloud-review-prep --execute."
    )
    assert "Fix finalize-story readiness" not in result_data["next_action"]


def test_workflow_run_cloud_review_prep_can_refresh_existing_packet_files(
    tmp_path: Path,
) -> None:
    story_path = create_story(tmp_path)
    (story_path / "status.yaml").write_text("ready_for_review: true\n", encoding="utf-8")
    review_bundle_path = story_path / "review_bundle"
    review_bundle_path.mkdir(exist_ok=True)
    (review_bundle_path / "manifest.yaml").write_text(
        "schema_version: 2\n"
        "repository:\n  head_sha: abcdef\n"
        "committed_diff:\n  staged_files: []\n"
        "working_tree:\n  classification: clean\n"
        "validation:\n  strict_clean_passed: true\n  host_container_git_match: true\n"
        "host:\n  status: passed\n  matched: true\n"
    )
    (story_path / "reports").mkdir(exist_ok=True)
    (story_path / "reports" / "quality_gate_result.yaml").write_text("status: READY_FOR_REVIEW\n", encoding="utf-8")
    
    write_finalize_result(story_path, ready_for_review=True)
    packet_path = story_path / "cloud_review_packet"
    packet_path.mkdir(exist_ok=True)
    prompt_path = packet_path / "cloud_review_prompt.md"
    prompt_path.write_text("old prompt\n", encoding="utf-8")

    first_result = run_workflow_run(
        tmp_path,
        STORY,
        phase=CLOUD_REVIEW_PREP_PHASE,
        execute=True,
    )
    refreshed_prompt = prompt_path.read_text(encoding="utf-8")
    second_result = run_workflow_run(
        tmp_path,
        STORY,
        phase=CLOUD_REVIEW_PREP_PHASE,
        execute=True,
    )
    result_data = read_yaml(second_result.result_path)

    assert first_result.status == "completed"
    assert second_result.status == "completed"
    assert "old prompt" not in refreshed_prompt
    assert "Use --force to overwrite" not in "\n".join(
        step.summary for step in second_result.step_results
    )
    assert second_result.safe_steps_executed == CLOUD_REVIEW_PREP_STEPS
    assert [step_result["step"] for step_result in result_data["step_results"]] == (
        CLOUD_REVIEW_PREP_STEPS
    )
    assert_workflow_run_safety_flags(result_data)


def test_prepare_safe_steps_are_hardcoded_allowlist(tmp_path: Path) -> None:
    steps = build_safe_steps(tmp_path, STORY, PREPARE_PHASE)

    assert [step.name for step in steps] == PREPARE_STEPS
    assert [step.command[0] for step in steps] == ["agentic", "agentic", "agentic"]
    assert [step.command[1] for step in steps] == PREPARE_STEPS
    for step in steps:
        assert "--project" in step.command
        assert "--story" in step.command
        assert STORY in step.command
        assert "prompt_pack" not in step.command
        assert not any(token in step.command for token in ["git", "push", "merge", "deploy"])


def test_local_finalize_safe_steps_are_hardcoded_allowlist(tmp_path: Path) -> None:
    steps = build_safe_steps(tmp_path, STORY, LOCAL_FINALIZE_PHASE)

    assert [step.name for step in steps] == LOCAL_FINALIZE_STEPS
    assert [step.command[0] for step in steps] == ["agentic", "agentic", "agentic", "agentic"]
    assert [step.command[1] for step in steps] == LOCAL_FINALIZE_STEPS
    for step in steps:
        assert "--project" in step.command
        assert "--story" in step.command
        assert STORY in step.command
        assert not any(token in step.command for token in ["git", "push", "merge", "deploy"])


def test_cloud_review_prep_safe_steps_are_hardcoded_allowlist(tmp_path: Path) -> None:
    steps = build_safe_steps(tmp_path, STORY, CLOUD_REVIEW_PREP_PHASE)

    assert [step.name for step in steps] == CLOUD_REVIEW_PREP_STEPS
    assert [step.command[0] for step in steps] == ["agentic", "agentic"]
    assert [step.command[1] for step in steps] == CLOUD_REVIEW_PREP_STEPS
    assert steps[0].command[-1] == "--force"
    for step in steps:
        assert "--project" in step.command
        assert "--story" in step.command
        assert STORY in step.command
        assert "prompt_pack" not in step.command
        assert not any(token in step.command for token in ["git", "push", "merge", "deploy"])


def test_workflow_run_does_not_run_arbitrary_commands_from_user_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_story(tmp_path)
    calls: list[str] = []

    def fail_if_shell_execution_is_used(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("workflow-run must not execute arbitrary shell commands")

    monkeypatch.setattr("subprocess.run", fail_if_shell_execution_is_used)

    result = run_workflow_run(
        tmp_path,
        STORY,
        execute=True,
        step_runner=fake_step_runner(calls),
    )
    result_data = read_yaml(result.result_path)

    assert calls == LOCAL_FINALIZE_STEPS
    assert result_data["ran_arbitrary_commands"] is False
    assert result_data["ran_destructive_commands"] is False


def test_workflow_run_prepare_does_not_run_arbitrary_commands_or_prompt_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    story_path = create_story(tmp_path)
    prompt_path = story_path / "prompt_pack" / "99_malicious_prompt.md"
    prompt_path.parent.mkdir()
    prompt_path.write_text("agentic deploy\n", encoding="utf-8")
    calls: list[str] = []

    def fail_if_shell_execution_is_used(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("workflow-run prepare must not execute shell commands")

    monkeypatch.setattr("subprocess.run", fail_if_shell_execution_is_used)

    result = run_workflow_run(
        tmp_path,
        STORY,
        phase=PREPARE_PHASE,
        execute=True,
        step_runner=fake_step_runner(calls),
    )
    result_data = read_yaml(result.result_path)
    serialized_commands = [
        step_result["command"] for step_result in result_data["step_results"]
    ]

    assert calls == PREPARE_STEPS
    assert prompt_path.name not in "\n".join(serialized_commands)
    assert "agentic deploy" not in "\n".join(serialized_commands)
    assert result_data["ran_arbitrary_commands"] is False
    assert result_data["ran_destructive_commands"] is False


def test_workflow_run_cloud_review_prep_does_not_run_arbitrary_commands_or_prompt_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    story_path = create_story(tmp_path)
    write_finalize_result(story_path, ready_for_review=True)
    prompt_path = story_path / "prompt_pack" / "99_malicious_prompt.md"
    prompt_path.parent.mkdir()
    prompt_path.write_text("agentic deploy\n", encoding="utf-8")
    calls: list[str] = []

    def fail_if_shell_execution_is_used(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("workflow-run cloud-review-prep must not execute shell commands")

    monkeypatch.setattr("subprocess.run", fail_if_shell_execution_is_used)

    result = run_workflow_run(
        tmp_path,
        STORY,
        phase=CLOUD_REVIEW_PREP_PHASE,
        execute=True,
        step_runner=fake_step_runner(calls),
    )
    result_data = read_yaml(result.result_path)
    serialized_commands = [
        step_result["command"] for step_result in result_data["step_results"]
    ]

    assert calls == CLOUD_REVIEW_PREP_STEPS
    assert prompt_path.name not in "\n".join(serialized_commands)
    assert "agentic deploy" not in "\n".join(serialized_commands)
    assert result_data["ran_arbitrary_commands"] is False
    assert result_data["ran_destructive_commands"] is False


def test_workflow_run_does_not_recommend_automatic_merge_or_deployment(
    tmp_path: Path,
) -> None:
    create_story(tmp_path)

    result = run_workflow_run(tmp_path, STORY)
    result_data = read_yaml(result.result_path)
    report = result.report_path.read_text(encoding="utf-8")

    recommendation_text = f"{result_data['next_action']}\n{report}".lower()
    assert "automatic merge" not in recommendation_text
    assert "automatic deployment" not in recommendation_text
    assert "human final approval is always required before merge" in recommendation_text
    assert result_data["committed_or_merged"] is False
    assert result_data["deployed"] is False


def test_cli_workflow_run_requires_story_argument(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["agentic", "workflow-run"])

    with pytest.raises(SystemExit) as error:
        main()

    assert error.value.code == 2


def test_cli_workflow_run_rejects_unsupported_phase_with_clear_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["agentic", "workflow-run", "--story", STORY, "--phase", "deploy"],
    )

    with pytest.raises(SystemExit) as error:
        main()

    captured = capsys.readouterr()
    assert error.value.code == 2
    assert "invalid choice: 'deploy'" in captured.err
    assert "prepare" in captured.err
    assert "local-finalize" in captured.err


def test_cli_workflow_run_defaults_project_to_current_directory_without_git_repo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    story_path = create_story(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["agentic", "workflow-run", "--story", STORY])

    main()

    output = capsys.readouterr().out
    assert f"Workflow run for {STORY}:" in output
    assert "Mode: planned safe local steps only" in output
    assert not (tmp_path / ".git").exists()
    assert (story_path / "reports" / "workflow_run_result.yaml").exists()
    assert (story_path / "reports" / "workflow_run_report.md").exists()
