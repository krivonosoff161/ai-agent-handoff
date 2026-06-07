# TASK — add retry/backoff to the HTTP client

## Outcome
`http_client.get()` retries transient failures (429, 5xx, network) with exponential
backoff, capped at 3 attempts, and surfaces the final error unchanged.

## Data
- `src/net/http_client.py` — the current client.
- `tests/test_http_client.py` — existing tests.

## Action
1. Add a retry loop around the request with `min(2**attempt, 8)`s sleep.
2. Retry only on 429 / 5xx / network errors; pass through 4xx immediately.
3. Add a `max_retries` parameter (default 2).

## Format
Edit `http_client.py` + add 2 tests. Note the change in `SESSION.md` return block.

## Done when
`pytest tests/test_http_client.py` is green and a forced-500 retries then raises.

## Boundaries — do NOT touch
Auth / secret handling, `.env`, production config.
