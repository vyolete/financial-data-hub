# FDH-001 — Financial Data Discovery & Catalog

Status: Draft (requires maintainer approval before implementation)
 
## User scenarios
An analyst searches financial datasets, filters by source and category, opens metadata and sees access and license status. An operator runs discovery and sees actual results or explicit failure.

## Requirements
- FDH-001-FR-01: Discover datasets via Socrata Discovery API with configurable queries and bounded pagination.
- FDH-001-FR-02: Deduplicate by provider and dataset ID; retain search provenance.
- FDH-001-FR-03: Persist metadata and run records in PostgreSQL; repeated discovery must not duplicate datasets.
- FDH-001-FR-04: Expose paginated search, filters and dataset details through FastAPI.
- FDH-001-FR-05: Display actual catalog records and run status in a React portal; distinguish empty, loading and failed states.
- FDH-001-FR-06: Add World Bank as a second discovery adapter after verifying its API and terms.
- FDH-001-NFR-01: Bounded requests, timeouts, retry policy, sanitized logs and no secrets in Git.
- FDH-001-NFR-02: Record official source URL, verification date, access and redistribution status; unknown terms remain unknown.
- FDH-001-NFR-03: Reproducible tests and evidence; no fabricated results.

## Acceptance
Given a verified live source, discovery returns actual metadata and the same records appear in the API and portal. Repeating the run does not duplicate records. Given an HTTP error, the run records failure and the portal does not report success. Unknown licenses are visible as pending. A second adapter uses the same catalog contract. Automated tests cover pagination, deduplication, failures and API filters; live smoke tests record evidence separately.

## Out of scope
Bulk financial data ingestion, scheduled pipelines, dlt/Dagster integration, financial analytics and production deployment. These are later slices.
