from __future__ import annotations

from pydantic import BaseModel

from src.model.enums import DocumentCategory
from src.services.repo_scanner_service import CandidateStatus, CoverageReport, ScanCandidate


class ScanCandidateResponseDTO(BaseModel):
    candidate_id: str
    relative_path: str
    filename: str
    size_bytes: int
    suggested_category: DocumentCategory | None
    confidence: float
    reason: str
    status: CandidateStatus

    @classmethod
    def from_entity(cls, candidate: ScanCandidate) -> ScanCandidateResponseDTO:
        return cls(
            candidate_id=candidate.candidate_id,
            relative_path=candidate.relative_path,
            filename=candidate.filename,
            size_bytes=candidate.size_bytes,
            suggested_category=candidate.suggested_category,
            confidence=candidate.confidence,
            reason=candidate.reason,
            status=candidate.status,
        )


class CoverageReportResponseDTO(BaseModel):
    scan_session_id: str
    candidates: list[ScanCandidateResponseDTO]
    missing_categories: list[DocumentCategory]

    @classmethod
    def from_entity(cls, scan_session_id: str, report: CoverageReport) -> CoverageReportResponseDTO:
        return cls(
            scan_session_id=scan_session_id,
            candidates=[ScanCandidateResponseDTO.from_entity(c) for c in report.candidates],
            missing_categories=report.missing_categories,
        )
