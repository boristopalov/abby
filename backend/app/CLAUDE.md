# Code Rules

## Priorities

Correctness > simplicity > readability > performance.

Before adding or refactoring, ask: is there a simpler, more elegant structure that already serves this need? Prefer fewer abstractions that do more, not more abstractions that each do one thing. Narrow, single-use helpers are a code smell. Interfaces should be wide and composable.

---

## Package management

Use `uv` exclusively. Never use `pip` directly.

---

## Architecture

The app is layered. Each layer has a single responsibility and must not reach into layers below its immediate dependency.

```
HTTP / WebSocket  (main.py, routes.py)
      ↓
  Service layer   (agent.py → ChatService)
      ↓
 Repositories     (db/chat_repository.py, db/project_repository.py)
 Ableton client   (ableton_client.py → AbletonClient)
      ↓
  Domain models   (models.py, db/models.py)
```

### Contracts

**Transport/infra (`_AbletonConnection`)** — raw TCP framing, request routing, reconnection. No domain knowledge.

**`AbletonClient`** — the only code that sends commands to Ableton. Returns typed domain models, never raw dicts. All Ableton access in the app goes through this class.

**Repositories** — the only code that reads/writes the database. Accept a SQLAlchemy `Session`; never create one. No business logic.

**`ChatService`** — owns all agent orchestration logic. Routes and WebSocket handlers must not contain business logic; they call into `ChatService` and stream results.

**Routes / WebSocket handlers** — handle connection lifecycle, validation, and serialization. No business logic. Construct services via FastAPI `Depends`.

**Domain models** — pure data (Pydantic). No I/O, no DB access, no side effects.

### Rules

- **Do not bypass layers.** Routes must not call `AbletonClient` directly for business purposes; that belongs in a service. Services must not instantiate DB sessions.
- **FastAPI `Depends` is the DI mechanism.** Services and repositories are injected, not constructed inline (exception: `ChatService` may be constructed in the WS handler where the injected deps are composed).
- **All Ableton state goes through `AbletonClient`.** No raw TCP or protocol details leak into services or routes.
- **Repositories return ORM models or domain types.** Never return raw SQL result rows.
- **New features that add Ableton capabilities add a typed method to `AbletonClient`** and a corresponding `AgentTool` in `agent.py`. Do not call `send_raw_command` from agent tools unless strictly necessary.
