# Documentation

This directory documents what the repository implements, why it was built that
way and where the implementation stops. Planned capabilities are marked as
planned.

## Start here

- [Product overview](product-overview.md): the problem, the advisory-model
  principle, the end-to-end flow, document outcomes, the reliability model and
  a capability table separating implemented from planned work.
- [Security and limitations](security-and-limitations.md): the local trust
  boundary and the controls that do not exist yet. Read it before assuming any
  capability.

## How it works

Read in this order to follow one document through the system.

1. [Runtime system map](architecture.md#runtime-system-map): the processes,
   who owns which state, and how they connect.
2. [Upload idempotency](architecture.md#upload-idempotency) and the
   [PDF acceptance boundary](architecture.md#pdf-acceptance-boundary): what
   happens before a document is registered.
3. [Durable workflow handoff](architecture.md#durable-workflow-handoff): the
   dispatcher, the Temporal workflow and each processing stage.
4. [Terminal workflow failures](architecture.md#terminal-workflow-failures):
   how an exhausted retry becomes safe, visible evidence.
5. [Advisory execution contract](architecture.md#advisory-execution-contract):
   the optional model stage and its persisted lifecycle.
6. [Persistence model](architecture.md#persistence-model) and
   [local blob lifecycle](architecture.md#local-blob-lifecycle): processing-run
   lineage and content-addressed storage.
7. [HTTP API contract](contracts/document-platform.openapi.json): the
   versioned OpenAPI document used to generate the console's API types.

## Evaluation

- [Evaluation](evaluation.md): the versioned synthetic corpus, the deterministic
  baseline and the local-model comparison.
- [Recorded results](evaluation/results/): benchmark runs with model, hardware
  and configuration.

## Decisions, releases and verification

- [Architecture decisions](decisions/): the significant choices and their
  consequences.
- [Release notes](releases/): what each milestone delivered and how it was
  verified.
- [Verification runbooks](runbooks/): the repeatable checks and observed
  results recorded for each release.
- [Repository history](history.md): the 2026-10-03 history rewrite and the
  old-to-new commit map.
