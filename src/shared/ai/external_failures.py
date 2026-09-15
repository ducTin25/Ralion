from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal


class ExternalFailureCode(StrEnum):
    CONNECTION = "connection"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    UNAVAILABLE = "unavailable"
    AUTHENTICATION = "authentication"
    BAD_REQUEST = "bad_request"
    PROTOCOL = "protocol"


@dataclass(eq=False)
class ExternalServiceFailure(Exception):  # noqa: N818 - approved application contract name
    service: Literal["embedding", "llm"]
    code: ExternalFailureCode
    retryable: bool
    attempts: int = 1
    timeout_scope: Literal["attempt", "stage", "overall"] | None = None
    retry_after_seconds: float | None = None
    # Provider diagnostics are intentionally metadata-only.  They retain enough information to
    # distinguish a transient provider failure from a malformed request without ever carrying a
    # prompt, completion, credential, or full HTTP headers across the application boundary.
    provider_exception_type: str | None = None
    provider_status_code: int | None = None
    provider_error_message: str | None = None
    provider_request_id: str | None = None
    provider_endpoint: str | None = None

    def __post_init__(self) -> None:
        super().__init__(f"{self.service}:{self.code.value}")
