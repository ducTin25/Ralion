"""The authoritative demo/deployment knowledge corpus, indexed for evaluation.

`demo-data/` is the single source of truth for what Ralion actually knows in the demo/
deployment environment:

    POLICY  -> demo-data/company-policy/            (39 policy documents + a README that is
                                                     corpus documentation, NOT knowledge)
    PROJECT -> demo-data/thanos-io_project-knowledge/ (repository snapshot + test_upload/)

Every answerable golden case must be traceable to real text in one of those files. This module
is what makes that checkable without a database or an LLM: it indexes each document into
headed sections and verifies that a golden case's `quote` is a genuine, verbatim substring of
the section it claims to come from.

## What is knowledge and what is bookkeeping

`demo-data/company-policy/README.md`, `demo-data/thanos-io_project-knowledge/MANIFEST.json` and
`demo-data/thanos-io_project-knowledge/docs/proposals-*/README.md` describe the corpus rather
than being answerable knowledge. `scripts/ingest_demo_corpus.py` skips the policy README, and
the manifest is never ingested at all. `KNOWLEDGE_EXCLUDED` below records that boundary so a
golden case can never quietly source an expected answer from manifest bookkeeping -- the
`validate_golden` check rejects any expected-evidence reference into these files.

The two `proposals-*/README.md` files ARE ingested (they are real index pages in the repository
snapshot and the runtime exposes them as documents), so they stay eligible as evidence -- but
only for catalog-ish questions where an index page genuinely is the answer.

## Resolving a golden document reference to a runtime document

`doc_id` is stable and human-readable, and each document records the `source_url` suffix the
runtime stores, so a live harness can map a retrieved citation back to a golden document
without guessing:

    POLICY   doc_id = policy document code  e.g. "IT-POL-003"
             source_url = "demo-data/company-policy/it_03_vpn_remote_access.md"
    PROJECT  doc_id = repo-relative path    e.g. "docs/contributing/coding-style-guide.md"
             source_url = ".../blob/main/<path>"            (repository snapshot)
                       or "demo-data/thanos-io_project-knowledge/test_upload/<file>"
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
POLICY_DIR = REPO_ROOT / "demo-data" / "company-policy"
PROJECT_DIR = REPO_ROOT / "demo-data" / "thanos-io_project-knowledge"

# Files under demo-data/ that describe the corpus instead of being answerable knowledge.
# Paths are relative to REPO_ROOT, forward-slashed.
KNOWLEDGE_EXCLUDED = frozenset(
    {
        "demo-data/company-policy/README.md",
        "demo-data/company-policy/manifest.json",
        "demo-data/company-policy/manifest_v2.json",
        "demo-data/thanos-io_project-knowledge/MANIFEST.json",
    }
)

# `test_upload/` documents are Ralion-authored onboarding guides rather than repository files;
# they reach the database through scripts/ingest_demo_corpus.py, not through GitHub sync.
_TEST_UPLOAD = "test_upload/"
_GITHUB_BLOB_PREFIX = "https://github.com/thanos-io/thanos/blob/main/"

_DOC_CODE = re.compile(r"^[-*]\s+\*\*Mã tài liệu:\*\*\s*(.+?)\s*$", re.MULTILINE)
_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_BOLD = re.compile(r"\*\*")
_WHITESPACE = re.compile(r"\s+")


def normalize(text: str) -> str:
    """The comparison form used for every quote check in the eval suite.

    Collapses all whitespace (so a quote may be re-wrapped in the golden file without breaking),
    strips markdown bold markers (so `**12 ngày**` matches `12 ngày`), and applies Unicode NFC.
    NFC matters here specifically: the Vietnamese corpus mixes precomposed and combining-diacritic
    forms, which are visually identical but different byte sequences -- without normalising, a
    correct quote can fail verification for a reason no human reviewer could see.

    Deliberately NOT case-folded: policy documents distinguish identifiers and proper nouns, and
    a case-insensitive match would let a golden case pass on text it does not really quote.
    """
    return _WHITESPACE.sub(" ", _BOLD.sub("", unicodedata.normalize("NFC", text))).strip()


@dataclass(frozen=True)
class Section:
    """One headed section: the heading line plus everything until the next heading of any level."""

    heading: str
    level: int
    path: str  # "3. Đăng ký và cấp quyền VPN" or "6. Xử lý sự cố VPN > 6.1. Tự kiểm tra..."
    line_start: int  # 1-indexed line of the heading itself
    line_end: int  # 1-indexed last line of the section body
    body: str

    @property
    def normalized(self) -> str:
        return normalize(f"{self.heading}\n{self.body}")


@dataclass(frozen=True)
class Document:
    doc_id: str
    domain: str  # POLICY | PROJECT
    path: str  # repo-relative, forward-slashed
    title: str
    source_url: str
    text: str
    sections: tuple[Section, ...] = field(repr=False, default=())

    @property
    def normalized(self) -> str:
        return normalize(self.text)

    def section(self, name: str) -> Section | None:
        """Look a section up by heading text or by full heading path, whitespace-insensitively.

        Accepts the bare heading (`"3. Đăng ký và cấp quyền VPN"`) or the full path with `>`
        separators, so a golden case can name a subsection unambiguously when two parents use
        the same subheading text.
        """
        wanted = normalize(name)
        for section in self.sections:
            if normalize(section.path) == wanted or normalize(section.heading) == wanted:
                return section
        return None

    def contains(self, quote: str) -> bool:
        return normalize(quote) in self.normalized


def _split_sections(text: str) -> tuple[Section, ...]:
    lines = text.splitlines()
    starts: list[tuple[int, int, str]] = []  # (line index, level, heading text)
    for index, line in enumerate(lines):
        match = _HEADING.match(line)
        if match:
            starts.append((index, len(match.group(1)), match.group(2).strip()))
    if not starts:
        return ()

    sections: list[Section] = []
    ancestors: list[tuple[int, str]] = []  # (level, heading)
    for position, (index, level, heading) in enumerate(starts):
        end = starts[position + 1][0] if position + 1 < len(starts) else len(lines)
        while ancestors and ancestors[-1][0] >= level:
            ancestors.pop()
        path = " > ".join([h for _, h in ancestors] + [heading])
        ancestors.append((level, heading))
        sections.append(
            Section(
                heading=heading,
                level=level,
                path=path,
                line_start=index + 1,
                line_end=end,
                body="\n".join(lines[index + 1 : end]).strip(),
            )
        )
    return tuple(sections)


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _load_policy() -> list[Document]:
    documents: list[Document] = []
    for path in sorted(POLICY_DIR.glob("*.md")):
        relative = _relative(path)
        if relative in KNOWLEDGE_EXCLUDED:
            continue
        text = path.read_text(encoding="utf-8")
        code_match = _DOC_CODE.search(text)
        if code_match is None:
            raise ValueError(
                f"{relative}: no '**Mã tài liệu:**' header. Either it is corpus documentation "
                "(add it to KNOWLEDGE_EXCLUDED) or it is a policy missing its code."
            )
        sections = _split_sections(text)
        title = sections[0].heading if sections and sections[0].level == 1 else path.stem
        documents.append(
            Document(
                doc_id=code_match.group(1).strip(),
                domain="POLICY",
                path=relative,
                title=title,
                source_url=relative,
                text=text,
                sections=sections,
            )
        )
    return documents


def _load_project() -> list[Document]:
    documents: list[Document] = []
    for path in sorted(PROJECT_DIR.rglob("*.md")):
        relative = _relative(path)
        if relative in KNOWLEDGE_EXCLUDED:
            continue
        repo_relative = path.relative_to(PROJECT_DIR).as_posix()
        text = path.read_text(encoding="utf-8")
        sections = _split_sections(text)
        title = sections[0].heading if sections and sections[0].level == 1 else path.stem
        source_url = (
            f"demo-data/thanos-io_project-knowledge/{repo_relative}"
            if repo_relative.startswith(_TEST_UPLOAD)
            else f"{_GITHUB_BLOB_PREFIX}{repo_relative}"
        )
        documents.append(
            Document(
                doc_id=repo_relative,
                domain="PROJECT",
                path=relative,
                title=title,
                source_url=source_url,
                text=text,
                sections=sections,
            )
        )
    return documents


class Corpus:
    """Indexed view over `demo-data/`. Build it once with `load_corpus()` (cached)."""

    def __init__(self, documents: list[Document]) -> None:
        self._by_id: dict[str, Document] = {}
        for document in documents:
            if document.doc_id in self._by_id:
                raise ValueError(f"duplicate doc_id {document.doc_id!r}")
            self._by_id[document.doc_id] = document

    def __len__(self) -> int:
        return len(self._by_id)

    def __iter__(self):
        return iter(self._by_id.values())

    def get(self, doc_id: str) -> Document | None:
        return self._by_id.get(doc_id)

    def documents(self, domain: str | None = None) -> list[Document]:
        return [d for d in self._by_id.values() if domain is None or d.domain == domain]

    def doc_ids(self, domain: str | None = None) -> list[str]:
        return [d.doc_id for d in self.documents(domain)]

    def by_source_url(self, source_url: str) -> Document | None:
        """Resolve a runtime citation's `source_url` back to a corpus document.

        Matches on suffix rather than equality: the repository snapshot is stored with a pinned
        commit SHA in some rows and `main` in others, and only the trailing repo-relative path is
        stable across both.
        """
        if not source_url:
            return None
        for document in self._by_id.values():
            if source_url == document.source_url:
                return document
        for document in self._by_id.values():
            suffix = document.doc_id if document.domain == "PROJECT" else document.path
            if source_url.endswith(suffix):
                return document
        return None

    def resolve_citation(self, source_url: str | None, source_title: str | None = None) -> Document | None:
        """Resolve a runtime citation back to a corpus document from whichever field actually
        carries a usable value.

        `ChatService._citation_source_url` deliberately withholds `source_url` on an ordinary
        citation -- it is populated only for an internal Conventions route, never for a real
        document (see that function). So for the common PROJECT/POLICY case the only real signal
        this eval harness gets is `source_title` (`RetrievalResult.document_title`, i.e. the
        `KnowledgeDocument.title` DB column), and that format is not guaranteed to match this
        module's own heading-derived `Document.title` guess: a document whose title was never set
        to a human-authored string (e.g. one carrying its raw ingest key/path instead, observed
        live as `"test_upload/thanos_environment_setup.md"`) still needs to resolve correctly.

        Every fallback below is an EXACT or suffix match against a real, stable corpus identifier
        (`title`, `doc_id`, `path`) -- never a fuzzy/substring guess -- so a citation for a
        document this corpus genuinely does not have still correctly resolves to `None` rather
        than fabricating a match.
        """
        if source_url:
            document = self.by_source_url(source_url)
            if document is not None:
                return document
        if not source_title:
            return None
        for document in self._by_id.values():
            if source_title == document.title:
                return document
        for document in self._by_id.values():
            if source_title == document.doc_id or source_title == document.path:
                return document
        for document in self._by_id.values():
            suffix = document.doc_id if document.domain == "PROJECT" else document.path
            if source_title.endswith(suffix):
                return document
        return None

    def verify_quote(self, doc_id: str, quote: str, section: str | None = None) -> str | None:
        """Returns None when the quote is genuine, else a human-readable reason it is not.

        When `section` is given the quote must appear *inside that section*, not merely somewhere
        in the document -- a quote that is real but attributed to the wrong section would send a
        human reviewer to the wrong place, and would make `expected_evidence` useless as a
        retrieval target.
        """
        document = self.get(doc_id)
        if document is None:
            return f"unknown doc_id {doc_id!r}"
        if not quote.strip():
            return "empty quote"
        if section is not None:
            found = document.section(section)
            if found is None:
                return f"{doc_id}: no section {section!r}"
            if normalize(quote) not in found.normalized:
                if document.contains(quote):
                    return f"{doc_id}: quote is real but not in section {section!r}"
                return f"{doc_id}: quote not found verbatim"
            return None
        if not document.contains(quote):
            return f"{doc_id}: quote not found verbatim"
        return None


@lru_cache(maxsize=1)
def load_corpus() -> Corpus:
    return Corpus(_load_policy() + _load_project())


def inventory() -> dict:
    """Machine-readable corpus inventory, used by the coverage matrix in the eval report."""
    corpus = load_corpus()
    documents = []
    for document in sorted(corpus, key=lambda d: (d.domain, d.doc_id)):
        documents.append(
            {
                "doc_id": document.doc_id,
                "domain": document.domain,
                "path": document.path,
                "title": document.title,
                "source_url": document.source_url,
                "bytes": len(document.text.encode("utf-8")),
                "sections": len(document.sections),
                "top_level_sections": [s.heading for s in document.sections if s.level == 2],
            }
        )
    return {
        "generated_from": "demo-data/",
        "knowledge_excluded": sorted(KNOWLEDGE_EXCLUDED),
        "totals": {
            "POLICY": len(corpus.documents("POLICY")),
            "PROJECT": len(corpus.documents("PROJECT")),
        },
        "documents": documents,
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Print or write the demo-data corpus inventory.")
    parser.add_argument("--write", type=Path, default=None, help="write the inventory JSON here")
    args = parser.parse_args()
    data = inventory()
    if args.write:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"wrote {args.write}")
    print(f"POLICY={data['totals']['POLICY']} PROJECT={data['totals']['PROJECT']}")
    for document in data["documents"]:
        print(f"  [{document['domain']:7s}] {document['doc_id']:55s} {document['sections']:3d} sections")


if __name__ == "__main__":
    main()
