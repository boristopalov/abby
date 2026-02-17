# Architecture

## Directory Structure

```
backend/
  app/
    main.py          — FastAPI app, WebSocket endpoints (/ws, /ws/audio)
    routes.py        — REST API routes (/api/projects, /api/sessions, etc.)
    agent.py         — Gemini AI agent with tool-calling (core business logic)
    ableton.py       — OSC client for Ableton Live communication
    sync.py          — Real-time parameter change monitoring via OSC listeners
    chat.py          — Chat context management (session/message state)
    tts.py           — Text-to-speech client (Fish Audio, optional)
    shared.py        — Genre prompts and shared constants
    logger.py        — Colored console logger
    db/
      __init__.py    — SQLAlchemy engine and session setup (SQLite at ./live.db)
      models.py      — ORM models (Project, Track, Device, Parameter, Clip, etc.)
      db_service.py  — Database service layer (all queries and mutations)
  AbletonOSC/        — Git submodule for OSC protocol

frontend/
  src/
    App.svelte       — Root component, project selection, layout
    types.d.ts       — TypeScript interfaces for all data types
    components/
      Chat.svelte          — Chat interface with track tagging (#trackname)
      SessionList.svelte   — Session management sidebar
      ParameterPanel.svelte — Real-time parameter change display
      ConnectionStatus.svelte — WebSocket connection indicator
      LoadingProgress.svelte  — Project loading/indexing progress
    lib/
      state.svelte.ts  — Global reactive state (Svelte 5 runes)
      wsStore.ts       — WebSocket connection and message handling
      sessionStore.ts  — Session persistence (localStorage)
      chatStore.ts     — Chat message store
      apiCalls.ts      — REST API client functions

audio_parser/        — Standalone audio analysis module (librosa, not yet integrated)
menubar/AbbyBar/     — macOS SwiftUI menubar app for voice input/output
```

## Data Flow

1. User selects/creates a project in the frontend
2. Backend indexes the Ableton session via OSC → stores structure in SQLite
3. Backend starts OSC listeners for all parameters (SyncService)
4. Frontend connects via WebSocket with `sessionId` and `projectId`
5. User sends chat messages → backend processes with Gemini agent
6. Agent uses tool-calling to query/modify Ableton state (reads from DB, writes via OSC)
7. Responses stream token-by-token back to the frontend
8. Parameter changes in Ableton are detected by SyncService → written to DB
9. Frontend polls `/api/parameter-changes` every 3 seconds

## Key Patterns

- **Singletons via FastAPI Depends + @lru_cache**: `get_agent()`, `get_ableton_client()`, `get_db_service()`, `get_sync_service()`
- **Reads from DB, writes via OSC**: The agent reads project structure from SQLite for speed, but sends parameter changes through OSC to Ableton
- **Streaming responses**: Agent yields chunks (`{"type": "text", "content": "..."}`) that stream over WebSocket
- **JSON key convention**: Backend uses snake_case internally, converts to camelCase for API responses via `snake_to_camel()`
- **Svelte 5 runes**: Frontend state uses `$state()` and `$derived()` — not legacy Svelte stores (except for a few writable stores in chatStore/sessionStore)
