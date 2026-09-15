"""Secret detection and redaction shared by every ingest, egress and output boundary.

Detection lives here once so that no boundary can drift to a weaker rule set.  Two
rule families make up the single ruleset, for reasons measured against the corpus
rather than chosen by taste:

* ``detect-secrets``' *named credential* plugins own the structured patterns (AWS
  keys, GitHub tokens, JWTs, private-key blocks, ...).  The generic Base64/Hex
  entropy plugins are deliberately excluded: they classify ordinary Markdown
  words, badge URLs and code identifiers as secrets.
* One explicitly-owned rule covers keyword assignments the library cannot reach.
  ``KeywordDetector`` only fires when the value is quoted, so ``token=<value>``
  and ``password: <value>`` — the common shape in prose-style policy documents —
  slip past it.  This is the *only* home-grown pattern, and it exists because the
  library set was measured to miss that shape, not as a general escape hatch.

Reaction is the caller's decision, not this module's: ingestion redacts before
chunk/embed/persist, the precomputed-embedding importer rejects (redaction there
would desynchronise content from its already-computed vector), external egress and
user-facing output redact.

Secret values are never logged, never persisted and never placed in a finding.
``detect-secrets`` is imported lazily inside this module so that no caller depends
on the concrete library.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.infrastructure.observability.step_logging import log_step_event

REDACTION_PLACEHOLDER = "[REDACTED]"

# Named credential detectors only.  Keep this list here: it is the single source of
# truth for what the application considers a secret.
_PLUGIN_NAMES = (
    "ArtifactoryDetector",
    "AWSKeyDetector",
    "AzureStorageKeyDetector",
    "BasicAuthDetector",
    "CloudantDetector",
    "DiscordBotTokenDetector",
    "GitHubTokenDetector",
    "GitLabTokenDetector",
    "IbmCloudIamDetector",
    "IbmCosHmacDetector",
    "JwtTokenDetector",
    "KeywordDetector",
    "MailchimpDetector",
    "NpmDetector",
    "OpenAIDetector",
    "PrivateKeyDetector",
    "PypiTokenDetector",
    "SendGridDetector",
    "SlackDetector",
    "SoftlayerDetector",
    "SquareOAuthDetector",
    "StripeDetector",
    "TelegramBotTokenDetector",
    "TwilioKeyDetector",
)

# The single home-grown rule.  Group ``value`` marks the span to redact so the key
# name survives, matching how the library plugins are applied below: a redaction
# that erased ``api_key:`` too would damage document structure and answer
# readability for no security gain.
_ASSIGNMENT_RULE_ID = "Keyword Assignment"
# Markdown emphasis is allowed around the key and the separator: HR policy documents write
# credentials as ``- **api_key:** value``, and a pattern that only accepted the bare
# ``api_key: value`` shape would miss precisely the corpus F-20 was raised for.
_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(?:api[_-]?key|secret[_-]?key|access[_-]?key|secret|token|password|passwd|pwd)"
    r"(?:\*{1,2}|_{1,2})?\s*[:=]\s*(?:\*{1,2}|_{1,2})?\s*['\"]?(?P<value>[^\s'\"]{8,})",
)

# The second home-grown rule, and the reason it cannot be left to the library:
# scanning is line-based, so ``PrivateKeyDetector`` flags the ``-----BEGIN`` header
# while the base64 body — the actual key material — stays on the following lines and
# survives.  This rule removes the whole block before line scanning begins.
_PRIVATE_KEY_BLOCK_RULE_ID = "Private Key Block"
_PRIVATE_KEY_BLOCK_PATTERN = re.compile(
    r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----[\s\S]*?-----END (?:[A-Z ]+ )?PRIVATE KEY-----",
)



@dataclass(frozen=True)
class SecretFinding:
    """A detection, identified by rule and position only — never by value."""

    rule_id: str
    line_number: int


@dataclass(frozen=True)
class RedactionResult:
    redacted_content: str
    findings: tuple[SecretFinding, ...]

    @property
    def has_findings(self) -> bool:
        return bool(self.findings)


class SecretScanUnavailableError(RuntimeError):
    """The scanner could not run. Every boundary must fail closed on this."""


def _library_matches(line: str) -> list[tuple[str, str]]:
    """``(rule_id, secret_value)`` pairs reported by the library for one line."""
    from detect_secrets.core.scan import scan_line

    return [(match.type, match.secret_value) for match in scan_line(line) if match.secret_value]


def _assignment_matches(line: str) -> list[tuple[str, str]]:
    return [
        (_ASSIGNMENT_RULE_ID, match.group("value"))
        for match in _ASSIGNMENT_PATTERN.finditer(line)
    ]


def _redact_private_key_blocks(content: str) -> tuple[str, list[SecretFinding]]:
    findings: list[SecretFinding] = []

    def replace(match: re.Match[str]) -> str:
        line_number = content.count("\n", 0, match.start()) + 1
        findings.append(
            SecretFinding(rule_id=_PRIVATE_KEY_BLOCK_RULE_ID, line_number=line_number)
        )
        return REDACTION_PLACEHOLDER

    return _PRIVATE_KEY_BLOCK_PATTERN.sub(replace, content), findings


def _redact_line(line: str, values: list[str]) -> str:
    """Replace every whitespace-delimited token that contains a detected value.

    Token granularity rather than exact-value granularity, because the library
    sometimes reports a prefix of the credential (``ghp`` for a GitHub token, the
    header and payload of a JWT without its signature).  Replacing only that prefix
    would leave the bulk of the credential in place — a worse outcome than a
    slightly wider redaction.  Whitespace and indentation are preserved, so the
    chunker still sees the document's structure.
    """

    def replace(match: re.Match[str]) -> str:
        token = match.group(0)
        return REDACTION_PLACEHOLDER if any(value in token for value in values) else token

    return re.sub(r"\S+", replace, line)



def scan(content: str) -> RedactionResult:
    """Detect and redact secrets in ``content``, line by line.

    Only the value a rule identified is replaced, so surrounding structure — the
    key name, a Markdown badge, a sentence — survives.  Redaction is idempotent:
    scanning already-redacted text yields no findings, which is what lets the
    GitHub path keep its own pre-ingest scan without special-casing.
    """
    try:
        from detect_secrets.settings import transient_settings
    except ImportError as exc:  # Fail closed: never persist or emit unscanned text.
        raise SecretScanUnavailableError(
            "detect-secrets is required for secret scanning at every boundary"
        ) from exc

    content, findings = _redact_private_key_blocks(content)
    lines = content.splitlines(keepends=True)
    with transient_settings({"plugins_used": [{"name": name} for name in _PLUGIN_NAMES]}):
        for index, line in enumerate(lines):
            matches = _library_matches(line) + _assignment_matches(line)
            # A value that carries the placeholder is the residue of an earlier
            # scan, not a secret. Ignoring it keeps redaction idempotent, which is
            # what lets the GitHub path keep its own pre-ingest scan.
            matches = [
                (rule_id, value)
                for rule_id, value in matches
                if REDACTION_PLACEHOLDER not in value
            ]
            if not matches:
                continue
            line_number = index + 1
            findings.extend(
                SecretFinding(rule_id=rule_id, line_number=line_number)
                for rule_id in sorted({rule_id for rule_id, _ in matches})
            )
            lines[index] = _redact_line(line, [value for _, value in matches])
    return RedactionResult(redacted_content="".join(lines), findings=tuple(findings))



def redact(value: str) -> tuple[str, bool]:
    """``scan`` for boundaries that only need the text and a "was anything hit" flag.

    Used by the user-facing output and external-egress boundaries, which react by
    redacting rather than by reporting individual findings.
    """
    result = scan(value)
    return result.redacted_content, result.has_findings


def record_secret_findings(
    result: RedactionResult,
    *,
    boundary: str,
    document_reference: str | None = None,
    trace_id: str | None = None,
) -> None:
    """Emit one structured line when a boundary redacted something.

    Rule ids, a count and a reference — never a value, never a line of content.
    Silent when nothing was found, so the log stays a signal rather than a trace.
    """
    if not result.findings:
        return

    log_step_event(
        event="secret_scan_redacted",
        boundary=boundary,
        rule_ids=sorted({finding.rule_id for finding in result.findings}),
        finding_count=len(result.findings),
        document_reference=document_reference,
        trace_id=trace_id,
    )

