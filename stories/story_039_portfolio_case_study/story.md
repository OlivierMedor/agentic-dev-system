# STORY-039: Portfolio Case Study and Interview Narrative

## Goal

Create public-facing portfolio documentation that explains agentic-dev-system as a professional software engineering project.

## Why This Matters

Recruiters, interviewers, and technical reviewers need a concise case study, interview narrative, and skills map that explain the project without exposing private prompts, operator strategy, secrets, or generated runtime artifacts.

## Acceptance Criteria

- Add Story 039 to blueprints/blueprint.yaml.
- Add docs/portfolio_case_study.md.
- Add docs/interview_talking_points.md.
- Add docs/skills_matrix.md.
- Update README.md to link to the three portfolio docs.
- Add or update tests that verify the new docs exist and README links to them.
- docs/portfolio_case_study.md explains the project overview, problem statement, structure needed for agentic coding, solution architecture, ASCII workflow diagram, key features, safety model, testing strategy, CI/CD strategy, LangGraph usage, intentional non-automation, lessons learned, and future roadmap.
- docs/portfolio_case_study.md mentions review bundles, quality gates, LangGraph, CI/CD, and human approval.
- docs/interview_talking_points.md includes a 30-second pitch, 2-minute explanation, technical deep dive, LangGraph explanation, Docker/CI/CD explanation, safety controls explanation, personal build-and-learning explanation, likely interviewer questions, and suggested answers.
- docs/skills_matrix.md maps Python, Docker, CI/CD, pytest, Ruff, Git/GitHub workflow, YAML schemas/config, LangGraph, agentic workflow design, code review automation, safety/approval gates, and documentation.
- Each skills matrix entry includes where the skill appears in the repo, why it matters, and how to talk about it in interviews.
- Do not add new CLI behavior.
- Do not expose private prompts, private strategies, secrets, generated runtime artifacts, or local-only operator guidance.

## Not In Scope

- No new CLI behavior.
- No cloud model calls.
- No automatic merge, deployment, repository visibility change, GitHub metadata change, or approval.
- No private prompts, private strategy guidance, secrets, generated runtime artifacts, or local-only operator details.
- No generated review bundle, cloud review packet, remote dev validation, support queue, or feature scan runtime files in the commit.

## Definition of Done

- docker compose build passes.
- pytest passes.
- ruff passes.
- artifact-policy passes.
- public-readiness passes.
- runtime-config validate passes.
- project-status runs.
- Story 039 prepare workflow-run passes.
- Story 039 local-finalize workflow-run passes.
- Story 039 cloud-review-prep workflow-run passes.
- Review bundle is generated for Story 039 but generated bundle files are not committed.
- Story reports are written for development, testing, and local review.
