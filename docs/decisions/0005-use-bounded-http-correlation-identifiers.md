# ADR 0005: Use bounded HTTP correlation identifiers

## Status

Accepted

## Context

Operators need one stable identifier to connect an HTTP request, its response
and the related application logs. Echoing arbitrary client input into logs would
allow unbounded values and control characters to pollute operational data.

## Decision

The HTTP adapter accepts `X-Correlation-ID` only when it is 1 to 128 characters
and contains ASCII letters, digits, `.`, `_` or `-`. Missing or unsafe values are
replaced with a generated UUID. The effective identifier is stored in a
request-local context and returned in every completed HTTP response.

This identifier correlates work inside one HTTP request. It is not a substitute
for W3C Trace Context or distributed tracing across Temporal and other services.

## Consequences

- Clients and operators can refer to the same request without exposing business
  identifiers.
- Log fields remain bounded and resistant to line-break injection.
- Propagation into asynchronous workflow execution requires a separate tracing
  or workflow-metadata decision.
