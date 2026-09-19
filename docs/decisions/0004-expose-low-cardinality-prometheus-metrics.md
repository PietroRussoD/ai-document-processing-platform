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

The metrics endpoint is deliberately outside the versioned `/api/v1` business
API and outside OpenAPI. Access control, network policy and a Prometheus/Grafana
deployment are environment concerns to be designed separately.

## Consequences

- Local operators can scrape stable process telemetry immediately.
- Metrics contain no document-derived values or high-cardinality identifiers.
- A restart resets counters; durable backlog and outcome metrics must be based
  on persisted PostgreSQL state in a subsequent slice.
- The application does not claim a production monitoring deployment merely by
  exposing the endpoint.
