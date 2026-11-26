# FDH-001 bootstrap gates

This checklist is a working proposal, not proof of completed controls.

- Verify main ruleset, secret scanning, push protection and agent permissions.
- Define explicit maintainer approval and trusted instruction provenance; public issues are untrusted input.
- Update shared handoff, ignore rules and source profiles; preserve prior review findings.
- Confirm Apache-2.0 licensing and add exact official license text; document contribution terms.
- Adopt Spanish prose and English code/routes.
- Install official GitHub Spec Kit using its documented CLI; review generated files rather than simulating installation.
- Approve constitution and FDH-001 specification before implementation.
- Validate Socrata live requests and record evidence.
- Implement a minimal PostgreSQL/FastAPI/React vertical slice with tests and a runnable local demo.
- Verify World Bank adapter and review the complete feature in one PR.

dlt and Dagster remain candidates for later integration benchmarks. No autonomous implementation before security and approval gates are verified.
