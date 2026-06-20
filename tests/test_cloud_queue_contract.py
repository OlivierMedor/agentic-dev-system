from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from agentic_dev.cloud_queue.adapters import FakeGeminiAdapter, FakeOpenAIAdapter, ManualPacketAdapter
from agentic_dev.cloud_queue.export import request_template
from agentic_dev.cloud_queue.models import CloudQueueRequest


def sample_request() -> CloudQueueRequest:
    return CloudQueueRequest(
        request_id="CQ-1",
        story="story_063_structured_cloud_escalation_and_manual_packet_queue",
        title="Contract request",
        blocker_type="local_blocker",
        details="details",
        state="ready",
        prior_state="new",
        batch_id="batch-1",
        request_count=1,
        requirements=["AC-001"],
        writable_paths=["src/agentic_dev/cloud_queue/service.py"],
        created_at="2026-06-20T12:00:00+00:00",
        updated_at="2026-06-20T12:00:00+00:00",
    )


def test_canonical_request_template_has_no_provider_specific_fields() -> None:
    template = request_template(sample_request())
    serialized = str(template)
    assert "openai" not in serialized.lower()
    assert "gemini" not in serialized.lower()
    assert "model" not in template["claims"]


def test_manual_packet_adapter_normalizes_offline() -> None:
    adapter = ManualPacketAdapter()
    payload = {
        "response_id": "CQ-1-response",
        "request_id": "CQ-1",
        "batch_id": "batch-1",
        "response_schema_version": 1,
        "normalized_response": {"summary": "normalized"},
        "raw_response": "raw",
        "checksum": "checksum",
        "decision": "SAFE",
        "claims": {"applicable_requirements": ["AC-001"], "writable_paths": ["src/agentic_dev/cloud_queue/service.py"]},
        "adapter": "manual_packet",
    }

    result = adapter.normalize(payload, "raw")
    assert result.response.request_id == "CQ-1"
    assert result.response.adapter == "manual_packet"
    assert result.normalized_text == "raw"


def test_fake_openai_and_gemini_adapters_normalize_without_changing_schema() -> None:
    openai_adapter = FakeOpenAIAdapter()
    gemini_adapter = FakeGeminiAdapter()
    openai_payload = {
        "id": "CQ-1-response",
        "request_id": "CQ-1",
        "batch_id": "batch-1",
        "decision": "SAFE",
        "claims": {"applicable_requirements": ["AC-001"], "writable_paths": ["src/agentic_dev/cloud_queue/service.py"]},
        "output": {"summary": "normalized"},
    }
    gemini_payload = {
        "response_id": "CQ-1-response",
        "request": "CQ-1",
        "batch": "batch-1",
        "decision": "SAFE",
        "claims": {"applicable_requirements": ["AC-001"], "writable_paths": ["src/agentic_dev/cloud_queue/service.py"]},
        "content": {"summary": "normalized"},
    }

    openai_result = openai_adapter.normalize(openai_payload, "raw openai")
    gemini_result = gemini_adapter.normalize(gemini_payload, "raw gemini")

    assert openai_result.response.adapter == "openai"
    assert gemini_result.response.adapter == "gemini"
    assert openai_result.response.request_id == "CQ-1"
    assert gemini_result.response.request_id == "CQ-1"
    result = isolated_module_probe(
        """
import sys
from agentic_dev.cloud_queue.adapters import FakeGeminiAdapter, FakeOpenAIAdapter

openai_adapter = FakeOpenAIAdapter()
gemini_adapter = FakeGeminiAdapter()
openai_adapter.normalize({
    "id": "CQ-1-response",
    "request_id": "CQ-1",
    "batch_id": "batch-1",
    "decision": "SAFE",
    "claims": {"applicable_requirements": ["AC-001"], "writable_paths": ["src/agentic_dev/cloud_queue/service.py"]},
    "output": {"summary": "normalized"},
}, "raw openai")
gemini_adapter.normalize({
    "response_id": "CQ-1-response",
    "request": "CQ-1",
    "batch": "batch-1",
    "decision": "SAFE",
    "claims": {"applicable_requirements": ["AC-001"], "writable_paths": ["src/agentic_dev/cloud_queue/service.py"]},
    "content": {"summary": "normalized"},
}, "raw gemini")
print("requests" in sys.modules)
print("httpx" in sys.modules)
"""
    )
    assert result == ["False", "False"]


def test_no_network_library_is_required_for_manual_contracts() -> None:
    result = isolated_module_probe(
        """
import sys
from agentic_dev.cloud_queue.adapters import ManualPacketAdapter
from agentic_dev.cloud_queue.export import request_template
from agentic_dev.cloud_queue.models import CloudQueueRequest

request = CloudQueueRequest(
    request_id="CQ-1",
    story="story_063_structured_cloud_escalation_and_manual_packet_queue",
    title="Contract request",
    blocker_type="local_blocker",
    details="details",
    state="ready",
    prior_state="new",
    batch_id="batch-1",
    request_count=1,
    requirements=["AC-001"],
    writable_paths=["src/agentic_dev/cloud_queue/service.py"],
    created_at="2026-06-20T12:00:00+00:00",
    updated_at="2026-06-20T12:00:00+00:00",
)
request_template(request)
ManualPacketAdapter()
print("requests" in sys.modules)
print("httpx" in sys.modules)
"""
    )
    assert result == ["False", "False"]


def isolated_module_probe(code: str) -> list[str]:
    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "src")
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return completed.stdout.strip().splitlines()
