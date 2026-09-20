# ADR 0004: Expose Low-Cardinality Prometheus Metrics

## Status

Accepted.

## Context

The asynchronous pipeline needs operational evidence that can be scraped and
compared across local runs without making a dashboard or a third-party service
part of the application. Request URLs, document identifiers, filenames, review
notes and text are unbounded or sensitive; using them as metric labels would
leak data and make Prometheus storage unreliable through high cardinality.

## Decision

Expose a local `GET /metrics` endpoint in Prometheus text format. Each API
application instance owns its registry, which keeps tests isolated and makes
process lifetime explicit.

The initial metric set contains build information and completed HTTP request
count and duration. Request labels are limited to HTTP method, matched route
template and status class. Instrumentation observes a response after route
handling and does not participate in document or workflow transactions.

Each scrape also refreshes a read-only PostgreSQL snapshot of current
processing-run counts by the bounded status enum and the age of the oldest
queued run. This is the authoritative backlog view after an application restart;
it is not a historical event counter.

The metrics endpoint is deliberately outside the versioned `/api/v1` business
API and outside OpenAPI. An optional Compose profile provides a pinned local
Prometheus scraper with seven-day retention and a file-provisioned Grafana
dashboard. Prometheus reaches the API running on the host; Grafana reaches
Prometheus over the Compose network. This stack does not define production
access control, network policy, alerting or storage.

## Consequences

- Local operators can scrape stable process telemetry immediately.
- Metrics contain no document-derived values or high-cardinality identifiers.
- A restart resets HTTP counters, while the processing backlog snapshot is
  reconstructed from PostgreSQL on the next scrape.
- Current status counts are not historical throughput or outcome-event totals;
  those require a separate event or audit design.
- The local Prometheus volume survives container replacement until explicitly
  removed, while its retention bounds disk use.
- The Grafana datasource and dashboard are version-controlled and read-only in
  the UI, preventing untracked demo configuration.
- The application does not claim a production monitoring deployment merely by
  exposing the endpoint.
