import asyncio
import json
import time
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .ableton_client import AbletonClient, get_ableton_client
from .agent import ChatService
from .analytics import AnalyticsService, get_analytics_service
from .db import SessionLocal
from .db.ableton_repository import AbletonRepository, get_ableton_repository
from .db.chat_repository import ChatRepository, get_chat_repository
from .db.models import init_db
from .db.project_repository import ProjectRepository, get_project_repository
from .events import (
    AppEvent,
    EventSender,
    IndexErrorEvent,
    IndexingStatusEvent,
    TracksEvent,
)
from .indexing import IndexingService
from .logger import logger
from .routes import router as api_router
from .sync import get_sync_service
from .tts import TextBuffer, TTSClient, get_tts_client

load_dotenv()

init_db()

app = FastAPI(title="Ableton Assistant")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix="/api")


def _make_sender(ws: WebSocket) -> EventSender:
    async def send(event: AppEvent) -> None:
        await ws.send_json(event.model_dump(exclude_none=True))

    return send


@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    sessionId: str,
    projectId: int,
    project_repo: ProjectRepository = Depends(get_project_repository),
    chat_repo: ChatRepository = Depends(get_chat_repository),
    ableton_repo: AbletonRepository = Depends(get_ableton_repository),
    ableton_client: AbletonClient = Depends(get_ableton_client),
    analytics: AnalyticsService = Depends(get_analytics_service),
):
    if not sessionId:
        logger.warning("[WS /ws] WebSocket connection attempt without session ID")
        await websocket.close(code=4000, reason="Session ID is required")
        return

    if not projectId:
        logger.warning("[WS /ws] WebSocket connection attempt without project ID")
        await websocket.close(code=4001, reason="Project ID is required")
        return

    project = project_repo.get_project(projectId)
    if not project:
        logger.warning(f"[WS /ws] Project not found: {projectId}")
        await websocket.close(code=4002, reason="Project not found")
        return

    chat_service = ChatService(chat_repo, ableton_repo, ableton_client)
    indexing_task = None
    session_start_time = time.monotonic()
    message_count = 0
    try:
        await websocket.accept()
        logger.info(
            f"[WS /ws] WebSocket connected - session: {sessionId}, project: {project.name}"
        )

        await ableton_client.start()
        send = _make_sender(websocket)

        existing_session = chat_repo.get_chat_session(sessionId)
        is_new_session = existing_session is None
        if is_new_session:
            logger.info(f"[WS /ws] Creating new chat session: {sessionId}")
            chat_repo.create_chat_session(f"Chat - {project.name}", sessionId)
            chat_repo.link_session_to_project(sessionId, projectId)

        analytics.capture(
            sessionId,
            "session_started",
            {"project_id": projectId, "mode": "text", "is_new_session": is_new_session},
        )

        if project.indexed_at is None:
            await send(IndexingStatusEvent(content=True))
            indexing_task = asyncio.create_task(
                _background_index(send, ableton_client, projectId, sessionId, analytics)
            )
        else:
            tracks_for_frontend = ableton_repo.get_project_tracks_for_frontend(
                projectId
            )
            await send(
                TracksEvent(
                    content=[t.model_dump(by_alias=True) for t in tracks_for_frontend]
                )
            )
            await send(IndexingStatusEvent(content=False))
            sync_service = get_sync_service(ableton_client)
            project_data = ableton_repo.load_project_structure(projectId)
            if project_data:
                sync_service.start_listeners(projectId, project_data)

        logger.info("[WS /ws] WebSocket setup complete")

        while True:
            data = await websocket.receive_json()
            msg = data.get("message")
            logger.info(f"[WS] Received WS Data: {data}")

            if msg == "[BLANK_AUDIO]" or not msg or not msg.strip():
                logger.debug("[WS /ws] Skipping blank/empty audio")
                continue

            if msg == "get-param-changes":
                logger.info("[WS /ws] Processing parameter changes request")
                changes_summary = ableton_repo.get_recent_parameter_changes()
                async for chunk in chat_service.process_message(
                    sessionId,
                    projectId,
                    {
                        "role": "user",
                        "content": json.dumps(
                            [c.model_dump() for c in changes_summary]
                        ),
                    },
                ):
                    await websocket.send_json(chunk.model_dump())
                    await asyncio.sleep(0)
                continue

            analytics.capture(
                sessionId,
                "message_sent",
                {
                    "project_id": projectId,
                    "mode": "text",
                    "message_index": message_count,
                },
            )
            message_count += 1

            logger.info(f"[WS /ws] Processing user message: {msg[:100]}...")
            async for chunk in chat_service.process_message(
                sessionId,
                projectId,
                {"role": "user", "content": msg},
            ):
                logger.info(f"[WS /ws] Sending chunk: {chunk}")
                await websocket.send_json(chunk.model_dump())
                await asyncio.sleep(0)

    except WebSocketDisconnect:
        logger.info(f"[WS /ws] WebSocket disconnected for session: {sessionId}")
        analytics.capture(
            sessionId,
            "session_ended",
            {
                "project_id": projectId,
                "mode": "text",
                "duration_seconds": time.monotonic() - session_start_time,
                "message_count": message_count,
            },
        )
        if indexing_task and not indexing_task.done():
            indexing_task.cancel()
        sync_service = get_sync_service(ableton_client)
        sync_service.stop_listeners()
    except Exception as e:
        logger.error(
            f"[WS /ws] WebSocket error for session {sessionId}: {str(e)}", exc_info=True
        )
        analytics.capture(
            sessionId,
            "session_ended",
            {
                "project_id": projectId,
                "mode": "text",
                "duration_seconds": time.monotonic() - session_start_time,
                "message_count": message_count,
            },
        )
        await websocket.close(code=1011, reason=str(e))
        if indexing_task and not indexing_task.done():
            indexing_task.cancel()
        sync_service = get_sync_service(ableton_client)
        sync_service.stop_listeners()


async def process_agent_with_tts(
    websocket: WebSocket,
    session_id: str,
    project_id: int,
    message: dict,
    chat_service: ChatService,
    tts_client: TTSClient,
):
    """Process agent message and stream TTS audio."""
    text_queue: asyncio.Queue[str | None] = asyncio.Queue()
    buffer = TextBuffer()

    async def text_from_queue():
        while True:
            item = await text_queue.get()
            if item is None:
                break
            yield item

    async def agent_consumer():
        async for chunk in chat_service.process_message(
            session_id, project_id, message
        ):
            if chunk.type == "text":
                sentences = buffer.add(chunk.content)
                for sentence in sentences:
                    await text_queue.put(sentence)
            elif chunk.type == "end_message":
                remaining = buffer.flush()
                if remaining:
                    await text_queue.put(remaining)
                await text_queue.put(None)
                await websocket.send_json(chunk.model_dump())
            else:
                await websocket.send_json(chunk.model_dump())

    async def tts_producer():
        try:
            async for audio_chunk in tts_client.stream_audio(text_from_queue()):
                await websocket.send_bytes(audio_chunk)
                await asyncio.sleep(0)
        except Exception as e:
            logger.error(f"[WS /ws/audio] TTS error: {e}")
            await websocket.send_json({"type": "error", "content": f"TTS error: {e}"})

    await websocket.send_json({"type": "audio_start"})
    await asyncio.gather(agent_consumer(), tts_producer())
    await websocket.send_json({"type": "audio_end"})


@app.websocket("/ws/audio")
async def websocket_audio_endpoint(
    websocket: WebSocket,
    sessionId: Optional[str] = None,
    projectId: Optional[int] = None,
    project_repo: ProjectRepository = Depends(get_project_repository),
    chat_repo: ChatRepository = Depends(get_chat_repository),
    ableton_repo: AbletonRepository = Depends(get_ableton_repository),
    ableton_client: AbletonClient = Depends(get_ableton_client),
    tts_client: Optional[TTSClient] = Depends(get_tts_client),
    analytics: AnalyticsService = Depends(get_analytics_service),
):
    if not sessionId:
        logger.warning("[WS /ws/audio] WebSocket connection attempt without session ID")
        await websocket.close(code=4000, reason="Session ID is required")
        return

    if not projectId:
        logger.warning("[WS /ws/audio] WebSocket connection attempt without project ID")
        await websocket.close(code=4001, reason="Project ID is required")
        return

    project = project_repo.get_project(projectId)
    if not project:
        logger.warning(f"[WS /ws/audio] Project not found: {projectId}")
        await websocket.close(code=4002, reason="Project not found")
        return

    if not tts_client:
        logger.warning("[WS /ws/audio] TTS client not available")
        await websocket.close(code=4003, reason="TTS not configured")
        return

    chat_service = ChatService(chat_repo, ableton_repo, ableton_client)
    indexing_task = None
    session_start_time = time.monotonic()
    message_count = 0
    try:
        await websocket.accept()
        logger.info(
            f"[WS /ws/audio] WebSocket connected - session: {sessionId}, project: {project.name}"
        )

        await ableton_client.start()
        send = _make_sender(websocket)

        existing_session = chat_repo.get_chat_session(sessionId)
        is_new_session = existing_session is None
        if is_new_session:
            logger.info(f"[WS /ws/audio] Creating new chat session: {sessionId}")
            chat_repo.create_chat_session(f"Chat - {project.name}", sessionId)
            chat_repo.link_session_to_project(sessionId, projectId)

        analytics.capture(
            sessionId,
            "session_started",
            {
                "project_id": projectId,
                "mode": "voice",
                "is_new_session": is_new_session,
            },
        )

        if project.indexed_at is None:
            await send(IndexingStatusEvent(content=True))
            indexing_task = asyncio.create_task(
                _background_index(send, ableton_client, projectId, sessionId, analytics)
            )
        else:
            tracks_for_frontend = ableton_repo.get_project_tracks_for_frontend(
                projectId
            )
            await send(
                TracksEvent(
                    content=[t.model_dump(by_alias=True) for t in tracks_for_frontend]
                )
            )
            await send(IndexingStatusEvent(content=False))
            sync_service = get_sync_service(ableton_client)
            project_data = ableton_repo.load_project_structure(projectId)
            if project_data:
                sync_service.start_listeners(projectId, project_data)

        logger.info("[WS /ws/audio] WebSocket setup complete")

        while True:
            data = await websocket.receive_json()
            msg = data.get("message")
            logger.info(f"[WS /ws/audio] Received WS Data: {data}")

            if msg == "[BLANK_AUDIO]" or not msg or not msg.strip():
                logger.debug("[WS /ws/audio] Skipping blank/empty audio")
                continue

            if msg == "get-param-changes":
                logger.info("[WS /ws/audio] Processing parameter changes request")
                changes_summary = ableton_repo.get_recent_parameter_changes()
                await process_agent_with_tts(
                    websocket,
                    sessionId,
                    projectId,
                    {
                        "role": "user",
                        "content": json.dumps(
                            [c.model_dump() for c in changes_summary]
                        ),
                    },
                    chat_service,
                    tts_client,
                )
                continue

            analytics.capture(
                sessionId,
                "message_sent",
                {
                    "project_id": projectId,
                    "mode": "voice",
                    "message_index": message_count,
                },
            )
            message_count += 1

            logger.info(f"[WS /ws/audio] Processing user message: {msg[:100]}...")
            await process_agent_with_tts(
                websocket,
                sessionId,
                projectId,
                {"role": "user", "content": msg},
                chat_service,
                tts_client,
            )

    except WebSocketDisconnect:
        logger.info(f"[WS /ws/audio] WebSocket disconnected for session: {sessionId}")
        analytics.capture(
            sessionId,
            "session_ended",
            {
                "project_id": projectId,
                "mode": "voice",
                "duration_seconds": time.monotonic() - session_start_time,
                "message_count": message_count,
            },
        )
        if indexing_task and not indexing_task.done():
            indexing_task.cancel()
        sync_service = get_sync_service(ableton_client)
        sync_service.stop_listeners()
    except Exception as e:
        logger.error(
            f"[WS /ws/audio] WebSocket error for session {sessionId}: {str(e)}",
            exc_info=True,
        )
        analytics.capture(
            sessionId,
            "session_ended",
            {
                "project_id": projectId,
                "mode": "voice",
                "duration_seconds": time.monotonic() - session_start_time,
                "message_count": message_count,
            },
        )
        await websocket.close(code=1011, reason=str(e))
        if indexing_task and not indexing_task.done():
            indexing_task.cancel()
        sync_service = get_sync_service(ableton_client)
        sync_service.stop_listeners()


async def _background_index(
    send: EventSender,
    ableton_client: AbletonClient,
    project_id: int,
    session_id: str,
    analytics: AnalyticsService,
) -> None:
    """Index a project from Ableton in the background, streaming events via send().

    On reconnect after a disconnect, already-indexed tracks are skipped so indexing
    resumes where it left off.
    """
    db = SessionLocal()
    try:
        project_repo = ProjectRepository(db)
        ableton_repo = AbletonRepository(db)
        indexing_service = IndexingService(ableton_client, project_repo, ableton_repo)

        analytics.capture(session_id, "indexing_started", {"project_id": project_id})
        index_start = time.monotonic()

        project_data = await indexing_service.index_project(project_id)
        tracks_for_frontend = ableton_repo.get_project_tracks_for_frontend(project_id)
        await send(
            TracksEvent(
                content=[t.model_dump(by_alias=True) for t in tracks_for_frontend]
            )
        )
        await send(IndexingStatusEvent(content=False))

        analytics.capture(
            session_id,
            "indexing_completed",
            {
                "project_id": project_id,
                "track_count": len(project_data),
                "device_count": sum(len(t.devices) for t in project_data),
                "duration_seconds": time.monotonic() - index_start,
            },
        )

        sync_service = get_sync_service(ableton_client)
        sync_service.start_listeners(project_id, project_data)

        logger.info(
            f"[BG_INDEX] Background indexing completed for project {project_id}"
        )

    except asyncio.CancelledError:
        analytics.capture(session_id, "indexing_abandoned", {"project_id": project_id})
        logger.info(f"[BG_INDEX] Indexing task cancelled for project {project_id}")
        raise
    except Exception as e:
        logger.error(
            f"[BG_INDEX] Indexing failed for project {project_id}: {e}", exc_info=True
        )
        try:
            await send(IndexErrorEvent(content=f"Indexing failed: {str(e)}"))
        except Exception:
            pass
    finally:
        db.close()


@app.get("/")
async def root():
    logger.info("[GET /] Root endpoint called")
    return {"message": "Ableton Assistant API"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
