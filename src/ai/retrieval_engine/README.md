# Retrieval engine

The only retrieval pipeline for both `PROJECT` and `POLICY` knowledge. Modules must pass domain, project, phase, and ACL filters instead of creating their own retrieval service.

The canonical dense query embedding is `BAAI/bge-m3`, normalized, with 1024 dimensions.

`RetrievalEngine` is the only chunk retrieval pipeline for both `PROJECT` and `POLICY`.
It applies domain/ACL predicates and the mandatory `DocumentVersion.status=ACTIVE`
predicate in SQL before cosine ranking. A document version is either `ACTIVE` (the
single current version) or `ARCHIVED` (citation history only); callers cannot widen
the retrieval scope to archived versions. POLICY queries never filter by `project_id`; PROJECT queries require it and
also require an ACTIVE project. It orchestrates a ParadeDB `pg_search` BM25 branch
in the identical scope, then combines candidates using Reciprocal Rank Fusion (RRF).
BM25 is lexical retrieval, not a sparse embedding. Candidate counts and RRF settings
are evaluation configuration rather than hard-coded relevance thresholds.
