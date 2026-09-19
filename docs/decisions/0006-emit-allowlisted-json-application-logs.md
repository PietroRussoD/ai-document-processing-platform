# ADR 0006: Emit allowlisted JSON application logs

## Status

Accepted

## Context

Plain-text messages are difficult to query consistently across the API,
dispatcher and worker. Serializing every attribute attached to a log record,
however, can expose secrets or create unbounded operational data.

## Decision

Application processes emit one JSON object per log event through a shared
standard-library formatter. Every record contains timestamp, level, service,
component, logger and message. Optional operational fields are serialized only
from an explicit allowlist.

Completed HTTP requests record the bounded correlation ID, method, matched route
template, status and duration. Raw URLs, query strings, headers, document data,
tokens and exception locals are not structured fields. Dispatcher outcome
counts use the same formatter. Temporal and third-party library messages may use
the formatter, but their message contents remain owned by those libraries.

## Consequences

- Logs can be parsed and filtered without a dedicated logging dependency.
- Correlation identifiers connect API responses to application request events.
- The allowlist must be extended deliberately when a new operational field is
  justified.
- Workflow-wide tracing still requires explicit Temporal context propagation.
