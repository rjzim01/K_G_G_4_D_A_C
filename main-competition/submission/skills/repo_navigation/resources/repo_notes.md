# Four repos, four sets of habits

Notes for the agent on what it is about to read. These are the source repos for
all 129 tasks: `fastapi/fastapi`, `Textualize/rich`, `psf/requests`, `encode/httpx`.

## fastapi

The heaviest of the four and the one with the most async. Routing lives in
`fastapi/routing.py`; a `bug` report naming a status code is usually about which
branch of `get_route_handler` or the response-model path returns it.

- `APIRoute`, `APIRouter` and their `matches()` / `handle()` methods
- `fastapi/routing.py::_prepare_response_content` and `serialize_response` —
  frequent sources of shape-mismatch bugs
- `fastapi/dependencies/utils.py` — dependency resolution, `solve_dependencies`
- Tests live in `tests/test_*`; heavy use of `httpx` and `anyio` markers, so a
  bare `pytest` will skip async tests unless `anyio` is configured. An async
  test that silently skips is worse than one that fails — check for skips.
- Optional dependencies: several features raise at import time if an extra is
  absent. That is environmental, not a bug in scope.

## httpx

Async-first client. The async and sync implementations are **duplicated**, not
shared: `AsyncClient` and `Client` each have their own transport, redirect and
response-streaming logic. A fix applied to one does **not** fix the other, and
the test suite asserts both. When you fix httpx, check whether the sync path has
the same defect — the hidden tests may cover the one you skipped.

- `httpx/_client.py`, `_transports/default.py`
- `httpx/_models.py` — `Response`, streaming
- `httpx/_auth.py`, `_content.py`

## rich

The most self-contained and usually the quickest. `Console` and its renderables
are the usual subject.

- `rich/console.py` — `Console.print`, `render`, segment machinery
- `rich/table.py`, `rich/text.py`, `rich/style.py` — the common task subjects
- `rich/live.py`, `rich/progress.py` — async and thread-sensitive
- Segment-level bugs produce wrong output rather than exceptions, so a test that
  "looks fine" may still be failing on an exact string comparison. Read the
  expected string in the test.

## requests

Oldest and least async. The usual subjects are adapters, hooks and cookie
handling.

- `requests/adapters.py`, `requests/sessions.py`
- `requests/cookies.py` — `RequestsCookieJar`, and the long tail of quoting and
  domain-matching rules
- `requests/models.py` — `Response`, streaming
- `urllib3` is vendored separately and mounted from `/wheels/`; a bug reported
  against requests may actually live in the pinned urllib3 version. Do not edit
  site-packages to fix one.

## Across all four

- The snapshot is frozen with forward history stripped, so `git log` shows a
  baseline commit and little else. `git log -S` and `git blame` are far less
  informative here than they normally would be. Do not waste budget on them.
- Tests import from the installed package, and `/wheels/` is mounted read-only.
  An editable install of the checkout is set up by `sandbox/setup.py`; if an
  import resolves to the wrong copy, that is environmental.
- Python 3.13 is in the container. `imp` and `telnetlib` are gone; compatibility
  shims exist in `docker/`. A failure mentioning either is environmental.
