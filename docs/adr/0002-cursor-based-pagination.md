# 2. Base64 Opaque Cursor Pagination for Parcel Listing

## Status

Accepted

## Context

Listing parcels with filtering and offset-based pagination leads to skipped or repeated items when earlier parcels change state between requests.

## Decision

We will implement base64-encoded opaque cursor pagination based on parcel sequence identity rather than numerical limits and offsets.

## Consequences

- Prevents data duplication or missing records during live state updates.
- Maintains consistent ordering across page navigation for clients.