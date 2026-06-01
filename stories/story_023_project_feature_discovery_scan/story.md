# STORY-023: Add project feature discovery scan

## Goal

Create commands that generate a project-level feature discovery packet and record structured feature suggestions into the feature queue.

## Why This Matters

The system should periodically ask what new capabilities would improve the project. Unlike story-level improvements, this loop looks at the whole project, current roadmap, queues, documentation, and optionally internet research performed by a cloud/research model. Suggestions should go into the feature queue for review instead of becoming work automatically.

## Acceptance Criteria

- Add feature-scan create command.
- Add feature-scan record command.
- feature-scan create defaults --project to the current working directory.
- feature-scan create creates .agentic/feature_scan/feature_scan_packet.md.
- feature-scan create creates .agentic/feature_scan/feature_suggestions_template.yaml.
- The feature scan packet includes project blueprint, project status summary, story list, queue counts, README summary, and relevant docs when present.
- The feature scan packet instructs the cloud/research model to consider internet research when available.
- The feature scan packet instructs the model to clearly separate project-derived observations from external/internet-derived observations.
- The feature scan packet instructs the model not to invent sources or claim internet research if it was not performed.
- feature-scan record requires --suggestions-file.
- feature-scan record validates suggestion YAML.
- feature-scan record creates feature queue items under .agentic/feature_queue/pending.
- Each feature item includes title, category, priority, details, expected_benefit, strategic_fit, evidence, source_urls, suggested_acceptance_criteria, and next_action.
- Runtime feature scan packet files are ignored by Git and blocked by artifact policy.
- Tests verify packet creation, template creation, suggestion validation, feature queue item creation, and artifact policy behavior.
- README documents the feature discovery workflow.

## Not In Scope

- No automatic internet browsing.
- No automatic cloud API call.
- No automatic story creation from feature suggestions.
- No automatic implementation of feature suggestions.
- No LangGraph yet.
- No web dashboard.

## Definition of Done

- pytest passes.
- ruff passes.
- artifact-policy passes.
- runtime-config validate passes.
- feature-scan create works.
- feature-scan record works with a sample suggestions file.
- finalize-story marks this story ready for review.
