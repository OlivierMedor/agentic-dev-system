from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from zipfile import ZipFile

from agentic_dev.cloud_batch.audit import BatchAuditEvent, append_batch_audit_event
from agentic_dev.cloud_batch.concurrency import acquire_batch_lock
from agentic_dev.cloud_batch.persistence import ensure_batch_dirs, load_batch_record, save_batch_record
from agentic_dev.cloud_batch.progress import derive_batch_progress, derive_batch_result
from agentic_dev.cloud_queue.importers import import_single_response
from agentic_dev.cloud_queue.persistence import checksum_bytes, now_iso
from agentic_dev.cloud_queue.validation import ensure_json_or_yaml_text, load_json_mapping, load_mapping_text, validate_archive


@dataclass(frozen=True)
class BatchImportResult:
    batch_id: str
    imported_count: int
    valid_count: int
    invalid_count: int
    skipped_count: int
    request_ids: tuple[str, ...]
    failed_members: tuple[str, ...]
    batch_checksum: str


def import_response_bundle(
    project_path: Path,
    bundle_path: Path,
    *,
    batch_id: str | None = None,
    event_id_factory: Callable[[], str] | None = None,
) -> BatchImportResult:
    ensure_batch_dirs(project_path)
    validate_archive(bundle_path)
    resolved_batch_id = batch_id or bundle_path.stem
    imported_count = valid_count = invalid_count = skipped_count = 0
    request_ids: list[str] = []
    failed_members: list[str] = []
    seen_request_ids: set[str] = set()
    with acquire_batch_lock(project_path, resolved_batch_id, "import"):
        with ZipFile(bundle_path) as archive:
            for member in sorted(archive.infolist(), key=lambda info: info.filename):
                if member.is_dir() or member.filename.endswith("manifest.yaml"):
                    continue
                imported_count += 1
                raw_bytes = archive.read(member)
                try:
                    raw_text = ensure_json_or_yaml_text(raw_bytes)
                    payload = load_json_mapping(raw_text) if member.filename.lower().endswith(".json") else load_mapping_text(raw_text)
                    request_id = str(payload.get("request_id", "")).strip()
                    if not request_id:
                        raise ValueError("Imported response is missing request_id.")
                    if request_id in seen_request_ids:
                        raise ValueError(f"Duplicate response within the bundle: {request_id}")
                    seen_request_ids.add(request_id)
                    result = import_single_response(
                        project_path,
                        response_data=payload,
                        raw_text=raw_text,
                        source_file=Path(member.filename),
                        event_id_factory=event_id_factory,
                    )
                    valid_count += result.valid_count
                    invalid_count += result.invalid_count
                    skipped_count += result.skipped_count
                    request_ids.extend(result.request_ids)
                except Exception:
                    invalid_count += 1
                    failed_members.append(member.filename)
    batch_checksum = checksum_bytes(bundle_path.read_bytes())
    if (ensure_batch_dirs(project_path).records / f"{resolved_batch_id}.yaml").exists():
        batch_record = load_batch_record(project_path, resolved_batch_id)
        updated_items = []
        for item in batch_record.items:
            if item.request_id in request_ids:
                updated_items.append(
                    type(item).from_dict(
                        {
                            **item.to_dict(),
                            "status": "responses_imported",
                        },
                    ),
                )
            else:
                updated_items.append(item)
        progress = derive_batch_progress(updated_items)
        result_status = "validation_partial" if invalid_count else "responses_imported"
        updated_batch_record = type(batch_record).from_dict(
            {
                **batch_record.to_dict(),
                "status": result_status,
                "items": [item.to_dict() for item in updated_items],
                "progress": progress.to_dict(),
                "checksums": {
                    **batch_record.checksums,
                    "response_bundle": batch_checksum,
                },
                "results": {
                    **derive_batch_result(batch_id, updated_items, []).to_dict(),
                    "status": result_status,
                    "checksum": batch_checksum,
                },
            },
        )
        save_batch_record(project_path, updated_batch_record)
    append_batch_audit_event(
        project_path,
        BatchAuditEvent(
            event_id="",
            event_type="batch_import",
            batch_id=resolved_batch_id,
            new_state="validation_partial" if invalid_count else "responses_imported",
            timestamp=now_iso(),
            details={
                "imported_count": imported_count,
                "valid_count": valid_count,
                "invalid_count": invalid_count,
            },
        ),
    )
    return BatchImportResult(
        batch_id=batch_id or bundle_path.stem,
        imported_count=imported_count,
        valid_count=valid_count,
        invalid_count=invalid_count,
        skipped_count=skipped_count,
        request_ids=tuple(request_ids),
        failed_members=tuple(failed_members),
        batch_checksum=batch_checksum,
    )
