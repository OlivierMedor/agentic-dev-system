from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

import yaml

from agentic_dev.cloud_queue.context import build_context, format_context_markdown
from agentic_dev.cloud_queue.models import (
    CloudQueueAuditEvent,
    CloudQueueExportResult,
    CloudQueueRequest,
    REQUEST_PACKET_CONTEXT_FILENAME,
    REQUEST_PACKET_EXPORT_FILENAME,
    REQUEST_PACKET_MANIFEST_FILENAME,
    REQUEST_PACKET_TEMPLATE_FILENAME,
)
from agentic_dev.cloud_queue.persistence import (
    append_audit_event,
    checksum_bytes,
    checksum_text,
    ensure_cloud_queue_dirs,
    move_request,
    now_iso,
)
from agentic_dev.cloud_queue.state_machine import validate_transition
from agentic_dev.cloud_queue.validation import ensure_request_count


def request_template(request: CloudQueueRequest) -> dict[str, Any]:
    return {
        "response_schema_version": request.response_schema_version,
        "response_id": f"{request.request_id}-response",
        "request_id": request.request_id,
        "batch_id": request.batch_id,
        "decision": "SAFE",
        "summary": "Describe the response here.",
        "claims": {
            "applicable_requirements": list(request.requirements),
            "writable_paths": list(request.writable_paths),
            "scope_changes": [],
            "dependency_status": "resolved",
            "resolved_dependencies": list(request.dependencies),
            "safe_to_apply": True,
        },
        "normalized_response": {
            "summary": "Normalized response content.",
        },
        "raw_response": "",
        "checksum": "",
        "adapter": "manual_packet",
    }


def format_export_markdown(
    request: CloudQueueRequest,
    request_context: str,
    template_text: str,
) -> str:
    return "\n".join(
        [
            "# Cloud Queue Export",
            "",
            "Manual-first export. Do not call any cloud API automatically.",
            "",
            f"Request ID: `{request.request_id}`",
            f"Batch ID: `{request.batch_id}`",
            f"Story: `{request.story}`",
            f"State: `{request.state}`",
            "",
            "## Request Context",
            "",
            request_context.rstrip(),
            "",
            "## Exact Response Template",
            "",
            template_text.rstrip(),
            "",
            "## Operator Notes",
            "",
            "- Upload the template manually to ChatGPT, Gemini, or another compatible model.",
            "- Return the raw answer without executing it.",
            "- Re-import the response for independent validation.",
            "- Approved responses are not automatically applied.",
        ],
    ).rstrip() + "\n"


def export_requests(
    project_path: Path,
    requests: list[CloudQueueRequest],
    batch_id: str,
    event_id_factory: Callable[[], str] | None = None,
) -> CloudQueueExportResult:
    ensure_request_count(requests)
    paths = ensure_cloud_queue_dirs(project_path)
    ordered = sorted(requests, key=lambda request: request.request_id)
    if not ordered:
        raise ValueError("No ready cloud queue requests were available for export.")

    export_dir = paths.exports / batch_id
    export_dir.mkdir(parents=True, exist_ok=True)
    export_path = export_dir / f"{batch_id}.zip"
    export_markdown_path = export_dir / f"{batch_id}.md"
    manifest_path = export_dir / REQUEST_PACKET_MANIFEST_FILENAME

    members: list[dict[str, Any]] = []
    with ZipFile(export_path, "w", compression=ZIP_DEFLATED) as archive:
        for request in ordered:
            validate_transition(request.state, "exported")
            updated = CloudQueueRequest.from_dict({**request.to_dict(), "prior_state": request.state, "state": "exported"})
            request_path = export_dir / f"{request.request_id}.yaml"
            request_path.write_text(yaml.safe_dump(updated.to_dict(), sort_keys=False), encoding="utf-8")
            context = build_context(
                project_path,
                request.story,
                request.title,
                request.details,
                requirements=request.requirements,
                writable_paths=request.writable_paths,
                dependencies=request.dependencies,
                blockers=request.notes,
                context_files=request.context_files,
            )
            request_context_text = format_context_markdown(context)
            template = yaml.safe_dump(request_template(updated), sort_keys=False)
            export_markdown = format_export_markdown(updated, request_context_text, template)

            request_yaml_bytes = yaml.safe_dump(updated.to_dict(), sort_keys=False).encode("utf-8")
            context_bytes = request_context_text.encode("utf-8")
            template_bytes = template.encode("utf-8")
            export_md_bytes = export_markdown.encode("utf-8")

            request_member = f"{request.request_id}/request.yaml"
            context_member = f"{request.request_id}/{REQUEST_PACKET_CONTEXT_FILENAME}"
            template_member = f"{request.request_id}/{REQUEST_PACKET_TEMPLATE_FILENAME}"
            export_member = f"{request.request_id}/{REQUEST_PACKET_EXPORT_FILENAME}"

            archive.writestr(request_member, request_yaml_bytes)
            archive.writestr(context_member, context_bytes)
            archive.writestr(template_member, template_bytes)
            archive.writestr(export_member, export_md_bytes)

            members.extend(
                [
                    {"path": request_member, "checksum": checksum_bytes(request_yaml_bytes)},
                    {"path": context_member, "checksum": checksum_bytes(context_bytes)},
                    {"path": template_member, "checksum": checksum_bytes(template_bytes)},
                    {"path": export_member, "checksum": checksum_bytes(export_md_bytes)},
                ],
            )

            event = CloudQueueAuditEvent(
                event_id="",
                event_type="export",
                request_id=request.request_id,
                batch_id=batch_id,
                prior_state=request.state,
                new_state="exported",
                packet_checksum=checksum_text(export_markdown),
                request_count=len(ordered),
                timestamp=now_iso(),
                details={
                    "member_count": 4,
                    "requirements": list(request.requirements),
                    "writable_paths": list(request.writable_paths),
                },
            )
            append_audit_event(project_path, event, event_id_factory=event_id_factory)

        manifest = {
            "schema_version": 1,
            "batch_id": batch_id,
            "request_ids": [request.request_id for request in ordered],
            "request_count": len(ordered),
            "members": members,
        }
        manifest_bytes = yaml.safe_dump(manifest, sort_keys=False).encode("utf-8")
        archive.writestr(REQUEST_PACKET_MANIFEST_FILENAME, manifest_bytes)

    packet_checksum = checksum_bytes(export_path.read_bytes())
    manifest["packet_checksum"] = packet_checksum
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    export_markdown_path.write_text(
        "\n".join(
            [
                "# Cloud Queue Export Index",
                "",
                f"Batch ID: `{batch_id}`",
                f"Request count: {len(ordered)}",
                f"Packet checksum: `{packet_checksum}`",
                "",
                "This ZIP archive is the canonical export artifact.",
            ],
        )
        + "\n",
        encoding="utf-8",
    )

    for request in ordered:
        moved = CloudQueueRequest.from_dict(
            {
                **request.to_dict(),
                "prior_state": request.state,
                "state": "exported",
                "packet_checksum": packet_checksum,
                "updated_at": now_iso(),
            }
        )
        move_request(project_path, moved, "exported", allow_overwrite=True)

    generated_files = [export_path, export_markdown_path, manifest_path]
    return CloudQueueExportResult(
        export_path=export_path,
        export_markdown_path=export_markdown_path,
        manifest_path=manifest_path,
        packet_checksum=packet_checksum,
        request_ids=[request.request_id for request in ordered],
        request_count=len(ordered),
        generated_files=generated_files,
    )
