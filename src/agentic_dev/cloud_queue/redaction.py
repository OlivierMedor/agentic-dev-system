from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("aws_access_key_id", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("aws_secret_access_key", re.compile(r"(?i)aws(.{0,20})?secret(.{0,20})?key")),
    ("bearer_token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-+/=]{8,}")),
    ("api_key", re.compile(r"(?i)\b[a-z0-9_-]*api[-_ ]?key\b")),
    ("password", re.compile(r"(?i)\bpassword\b\s*[:=]\s*[^\s]+")),
    ("cookie", re.compile(r"(?i)\bcookie\b\s*[:=]\s*[^\s]+")),
    ("authorization_header", re.compile(r"(?i)\bauthorization\b\s*[:=]\s*[^\s]+")),
    ("ssh_private_key", re.compile(r"-----BEGIN (?:OPENSSH|RSA|EC|PRIVATE) PRIVATE KEY-----")),
    ("pem_block", re.compile(r"-----BEGIN [A-Z0-9 ]+-----")),
    ("wallet_seed", re.compile(r"(?i)\b(seed phrase|mnemonic|wallet key)\b")),
    ("git_credentials", re.compile(r"(?i)https?://[^:\s]+:[^@\s]+@")),
    ("env_dump", re.compile(r"(?i)^(?:[A-Z_][A-Z0-9_]*=.+)$", re.MULTILINE)),
)

SENSITIVE_FILENAME_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)(^|[\\/])\.env(\..+)?$"),
    re.compile(r"(?i)(^|[\\/])id_rsa(\.pub)?$"),
    re.compile(r"(?i)(^|[\\/])credentials(\.json)?$"),
    re.compile(r"(?i)(^|[\\/])config(\.ini|\.toml)?$"),
)


@dataclass(frozen=True)
class RedactionSummary:
    filename_count: int
    content_count: int
    pattern_counts: dict[str, int]

    def to_dict(self) -> dict[str, int | dict[str, int]]:
        return {
            "filename_count": self.filename_count,
            "content_count": self.content_count,
            "pattern_counts": dict(self.pattern_counts),
        }


def is_sensitive_filename(relative_path: str | Path) -> bool:
    candidate = str(relative_path).replace("\\", "/")
    return any(pattern.search(candidate) for pattern in SENSITIVE_FILENAME_PATTERNS)


def redact_text(text: str) -> tuple[str, RedactionSummary]:
    redacted = text
    pattern_counts: dict[str, int] = {}
    content_count = 0

    for name, pattern in SECRET_PATTERNS:
        matches = list(pattern.finditer(redacted))
        if not matches:
            continue

        content_count += len(matches)
        pattern_counts[name] = len(matches)
        redacted = pattern.sub(f"[REDACTED:{name}]", redacted)

    return redacted, RedactionSummary(
        filename_count=0,
        content_count=content_count,
        pattern_counts=pattern_counts,
    )


def redact_path_fragment(relative_path: str) -> str:
    if is_sensitive_filename(relative_path):
        return "[REDACTED:FILENAME]"
    return relative_path

