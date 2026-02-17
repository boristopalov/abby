# Abby - AI Music Production Assistant

Abby is an AI assistant for music producers using Ableton Live. It connects to Ableton via OSC, indexes the project structure (tracks, devices, parameters, MIDI clips) into a local SQLite database, and lets users chat with an AI agent (Google Gemini) that can inspect and modify the live session. The frontend is a Svelte web app that communicates with the FastAPI backend over REST and WebSockets.

See @README.md for setup prerequisites and installation steps.

## Useful Commands

### Backend (from `backend/`)

```bash
uv sync                            # Install dependencies
uv run fastapi dev app/main.py     # Dev server (hot reload, :8000)
uv run ruff check app/             # Lint
uv run ruff format app/            # Format
uv run ruff check app/ --fix       # Auto-fix lint errors
# API docs at http://localhost:8000/docs
```

### Frontend (from `frontend/`)

```bash
npm install        # Install dependencies
npm run dev        # Dev server (:5173)
npm run check      # Type check (svelte-check + tsc)
```

### Git

```bash
# Clone with submodules (AbletonOSC lives in backend/AbletonOSC/)
git submodule update --init --recursive
```

### Environment

Backend requires a `.env` file in `backend/`:

```
GEMINI_API_KEY=...
# Optional TTS:
# FISH_API_KEY=...
# FISH_AUDIO_REFERENCE_ID=...
```

## Debugging

- **Backend logs** go to stdout (the terminal running `fastapi dev`). The custom logger in `backend/app/logger.py` uses colored output with `[LEVEL]` prefixes. Logs are tagged with route context like `[WS /ws]`, `[SYNC]`, etc.
- **No log files** — all logging is console-only. Check the terminal running the backend.
- **Database** is SQLite at `backend/live.db`. You can inspect it directly with `sqlite3 backend/live.db` to check project state, parameter history, chat sessions, etc.
- **OSC issues** — if the backend can't connect to Ableton, make sure Ableton is running with the AbletonOSC remote script installed. OSC communication happens on localhost.
- **WebSocket connection** — the frontend shows a connection status indicator. If it's disconnected, check the backend terminal for errors. The frontend auto-reconnects on disconnect.
- **Parameter sync** — the `SyncService` runs OSC listeners on a separate thread. If parameter changes aren't showing up, check `[SYNC]` log lines in the backend terminal.

## Architecture

See @ARCHITECTURE.md for directory structure, data flow, and key patterns.

## Important Files

When working on the AI agent behavior, tool definitions, or Ableton integration:
- `backend/app/agent.py` — agent logic, system prompt, tool schemas, function dispatch
- `backend/app/ableton.py` — all OSC communication with Ableton

When working on data persistence or the DB schema:
- `backend/app/db/models.py` — all SQLAlchemy models
- `backend/app/db/db_service.py` — all database queries

When working on real-time sync:
- `backend/app/sync.py` — OSC listener registration and parameter change handling

When working on the frontend:
- `frontend/src/App.svelte` — top-level layout and routing
- `frontend/src/lib/state.svelte.ts` — global reactive state
- `frontend/src/lib/wsStore.ts` — WebSocket connection management

## Styling

- Frontend uses **TailwindCSS** with a dark theme (gray-900 background, gray-100 text)
- Purple accent color for interactive elements (purple-500/600)
- No component library — all UI is custom Tailwind utility classes
- Keep styling consistent with existing components when adding new UI

## Guidance

### Must do
- **Lint before any commit**: run `uv run ruff check app/ && uv run ruff format --check app/` from `backend/` before committing Python changes. Fix any errors before proceeding.
- **Do not commit unless explicitly asked.** Do not auto-commit after changes.

### Conventions
- Only add comments when the logic isn't obvious from the code itself. Prefer clear naming over comments.
- Do not add docstrings, type annotations, or refactor code you didn't change.
- Keep changes minimal and focused on what was requested.
- Backend Python follows snake_case; frontend TypeScript follows camelCase.
- All parameter values in the system are normalized 0.0–1.0. Human-readable strings (e.g. "-12 dB", "4:1") are stored separately in `value_string`.
