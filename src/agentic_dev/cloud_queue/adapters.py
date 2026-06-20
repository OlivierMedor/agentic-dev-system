from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agentic_dev.cloud_queue.models import CloudQueueResponse
from agentic_dev.cloud_queue.persistence import checksum_text


@dataclass(frozen=True)
class AdapterNormalizationResult:
    response: CloudQueueResponse
    normalized_text: str


class ManualPacketAdapter:
    provider_name = "manual_packet"

    def normalize(self, payload: dict[str, Any], raw_text: str) -> AdapterNormalizationResult:
        response = CloudQueueResponse.from_dict(payload)
        if not response.response_id:
            raise ValueError("Manual packet payload must include response_id.")
        normalized_text = raw_text.strip()
        return AdapterNormalizationResult(response=response, normalized_text=normalized_text)


class FakeOpenAIAdapter:
    provider_name = "openai"

    def normalize(self, payload: dict[str, Any], raw_text: str) -> AdapterNormalizationResult:
        normalized = {
            "response_id": payload.get("id", ""),
            "request_id": payload.get("request_id", ""),
            "batch_id": payload.get("batch_id", ""),
            "response_schema_version": payload.get("response_schema_version", 1),
            "normalized_response": payload.get("output", {}),
            "raw_response": raw_text,
            "checksum": checksum_text(raw_text),
            "decision": payload.get("decision", "SAFE"),
            "claims": payload.get("claims", {}),
            "adapter": self.provider_name,
        }
        return AdapterNormalizationResult(
            response=CloudQueueResponse.from_dict(normalized),
            normalized_text=raw_text.strip(),
        )


class FakeGeminiAdapter:
    provider_name = "gemini"

    def normalize(self, payload: dict[str, Any], raw_text: str) -> AdapterNormalizationResult:
        normalized = {
            "response_id": payload.get("response_id", ""),
            "request_id": payload.get("request", ""),
            "batch_id": payload.get("batch", ""),
            "response_schema_version": payload.get("response_schema_version", 1),
            "normalized_response": payload.get("content", {}),
            "raw_response": raw_text,
            "checksum": checksum_text(raw_text),
            "decision": payload.get("decision", "SAFE"),
            "claims": payload.get("claims", {}),
            "adapter": self.provider_name,
        }
        return AdapterNormalizationResult(
            response=CloudQueueResponse.from_dict(normalized),
            normalized_text=raw_text.strip(),
        )

