# 1. Encapsulating Domain Lifecycle in a Pure Module

## Status

Accepted

## Context

We need to handle parcel state transitions and validation rules reliably without mixing business domain logic with web framework or infrastructure code.

## Decision

We will encapsulate the domain lifecycle and state machine inside a pure Python module (`app/domain.py`) with zero external API dependencies.

## Consequences

- The domain rules are fully testable in isolation without launching a web server.
- The HTTP layer in FastAPI stays clean and only acts as a wrapper around domain functions.