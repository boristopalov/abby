import asyncio
import time
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .ableton_client import AbletonClient, get_ableton_client
from .agent import ChatService
from .analytics import AnalyticsService, get_analytics_service
from .db.chat_repository import ChatRepository, get_chat_repository
from .db.models import init_db
from .db.project_repository import ProjectRepository, get_project_repository
from .events import AppEvent, EventSender
from .logger import logger
from .routes import router as api_router
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

    chat_service = ChatService(chat_repo, ableton_client)
    session_start_time = time.monotonic()
    message_count = 0
    try:
        await websocket.accept()
        logger.info(
            f"[WS /ws] WebSocket connected - session: {sessionId}, project: {project.name}"
        )

        await ableton_client.start()

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

        logger.info("[WS /ws] WebSocket setup complete")

        while True:
            data = await websocket.receive_json()
            logger.info(f"[WS] Received WS Data: {data}")

            if data.get("type") == "approval_response":
                logger.info(f"[WS /ws] Processing approval response for session: {sessionId}")
                async for chunk in chat_service.resume_with_approvals(
                    sessionId,
                    projectId,
                    data.get("approvals", {}),
                ):
                    logger.info(f"[WS /ws] Sending chunk: {chunk}")
                    await websocket.send_json(chunk.model_dump())
                    await asyncio.sleep(0)
                continue

            msg = data.get("message")
            if msg == "[BLANK_AUDIO]" or not msg or not msg.strip():
                logger.debug("[WS /ws] Skipping blank/empty audio")
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

    chat_service = ChatService(chat_repo, ableton_client)
    session_start_time = time.monotonic()
    message_count = 0
    try:
        await websocket.accept()
        logger.info(
            f"[WS /ws/audio] WebSocket connected - session: {sessionId}, project: {project.name}"
        )

        await ableton_client.start()

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

        logger.info("[WS /ws/audio] WebSocket setup complete")

        while True:
            data = await websocket.receive_json()
            msg = data.get("message")
            logger.info(f"[WS /ws/audio] Received WS Data: {data}")

            if msg == "[BLANK_AUDIO]" or not msg or not msg.strip():
                logger.debug("[WS /ws/audio] Skipping blank/empty audio")
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


@app.get("/")
async def root():
    logger.info("[GET /] Root endpoint called")
    return {"message": "Ableton Assistant API"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
