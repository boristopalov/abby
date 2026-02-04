import asyncio
import json
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .ableton import AbletonClient, get_ableton_client
from .agent import Agent, get_agent
from .chat import ChatContext, get_chat_context
from .db.db_service import DBService, get_db_service
from .db.models import init_db
from .logger import logger
from .routes import router as api_router
from .sync import get_sync_service
from .tts import TTSClient, TextBuffer, get_tts_client

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


@app.get("/")
async def root():
    logger.info("[GET /] Root endpoint called")
    return {"message": "Ableton Assistant API"}


@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    sessionId: Optional[str] = None,
    projectId: Optional[int] = None,
    db_service: DBService = Depends(get_db_service),
    ableton_client: AbletonClient = Depends(get_ableton_client),
    agent: Agent = Depends(get_agent),
    context: ChatContext = Depends(get_chat_context),
):
    if not sessionId:
        logger.warning("[WS /ws] WebSocket connection attempt without session ID")
        await websocket.close(code=4000, reason="Session ID is required")
        return

    if not projectId:
        logger.warning("[WS /ws] WebSocket connection attempt without project ID")
        await websocket.close(code=4001, reason="Project ID is required")
        return

    # Verify project exists
    project = db_service.get_project(projectId)
    if not project:
        logger.warning(f"[WS /ws] Project not found: {projectId}")
        await websocket.close(code=4002, reason="Project not found")
        return

    try:
        await websocket.accept()
        logger.info(
            f"[WS /ws] WebSocket connected - session: {sessionId}, project: {project.name}"
        )

        loop = asyncio.get_running_loop()
        ableton_client.set_websocket(websocket, loop)

        # Start sync listeners for real-time parameter updates
        sync_service = get_sync_service(ableton_client)
        project_data = db_service.load_project_structure(projectId)
        if project_data:
            sync_service.start_listeners(projectId, project_data)

        # Set up session
        context.set_session(sessionId, projectId)

        # Create chat session if needed
        session = db_service.get_chat_session(sessionId)
        if not session:
            logger.info(f"[WS /ws] Creating new chat session: {sessionId}")
            db_service.create_chat_session(f"Chat - {project.name}", sessionId)
            db_service.link_session_to_project(sessionId, projectId)

        # Send tracks info to frontend
        await websocket.send_json({"type": "loading_progress", "content": 10})
        tracks_for_frontend = db_service.get_project_tracks_for_frontend(projectId)
        await websocket.send_json({"type": "tracks", "content": tracks_for_frontend})
        await websocket.send_json({"type": "loading_progress", "content": 100})
        logger.info("[WS /ws] WebSocket setup complete")

        # Handle incoming messages
        while True:
            data = await websocket.receive_json()
            msg = data.get("message")
            logger.info(f"[WS] Received WS Data: {data}")

            # Skip blank audio markers - no speech detected
            if msg == "[BLANK_AUDIO]" or not msg or not msg.strip():
                logger.debug("[WS /ws] Skipping blank/empty audio")
                continue

            if msg == "get-param-changes":
                logger.info("[WS /ws] Processing parameter changes request")
                changes_summary = db_service.get_recent_parameter_changes()
                async for chunk in agent.process_message(
                    context,
                    {"role": "user", "content": json.dumps(changes_summary)},
                    db_service,
                    ableton_client,
                ):
                    await websocket.send_json(chunk)
                    await asyncio.sleep(0)
                continue

            logger.info(f"[WS /ws] Processing user message: {msg[:100]}...")
            async for chunk in agent.process_message(
                context,
                {"role": "user", "content": msg},
                db_service,
                ableton_client,
            ):
                logger.info(f"[WS /ws] Sending chunk: {chunk}")
                await websocket.send_json(chunk)
                await asyncio.sleep(0)

    except WebSocketDisconnect:
        logger.info(f"[WS /ws] WebSocket disconnected for session: {sessionId}")
        sync_service = get_sync_service(ableton_client)
        sync_service.stop_listeners()
        ableton_client.unset_websocket()
    except Exception as e:
        logger.error(
            f"[WS /ws] WebSocket error for session {sessionId}: {str(e)}", exc_info=True
        )
        await websocket.close(code=1011, reason=str(e))
        sync_service = get_sync_service(ableton_client)
        sync_service.stop_listeners()
        ableton_client.unset_websocket()


async def process_agent_with_tts(
    websocket: WebSocket,
    agent: Agent,
    context: ChatContext,
    message: dict,
    db_service: DBService,
    ableton_client: AbletonClient,
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
        """Consume agent output, queue text for TTS, send metadata to websocket."""
        async for chunk in agent.process_message(
            context, message, db_service, ableton_client
        ):
            msg_type = chunk.get("type")

            if msg_type == "text":
                sentences = buffer.add(chunk.get("content", ""))
                for sentence in sentences:
                    await text_queue.put(sentence)
            elif msg_type == "end_message":
                remaining = buffer.flush()
                if remaining:
                    await text_queue.put(remaining)
                await text_queue.put(None)  # Signal end
                await websocket.send_json(chunk)
            else:  # function_call, error
                await websocket.send_json(chunk)

    async def tts_producer():
        """Stream audio from TTS to websocket."""
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
    db_service: DBService = Depends(get_db_service),
    ableton_client: AbletonClient = Depends(get_ableton_client),
    agent: Agent = Depends(get_agent),
    context: ChatContext = Depends(get_chat_context),
    tts_client: Optional[TTSClient] = Depends(get_tts_client),
):
    if not sessionId:
        logger.warning("[WS /ws/audio] WebSocket connection attempt without session ID")
        await websocket.close(code=4000, reason="Session ID is required")
        return

    if not projectId:
        logger.warning("[WS /ws/audio] WebSocket connection attempt without project ID")
        await websocket.close(code=4001, reason="Project ID is required")
        return

    # Verify project exists
    project = db_service.get_project(projectId)
    if not project:
        logger.warning(f"[WS /ws/audio] Project not found: {projectId}")
        await websocket.close(code=4002, reason="Project not found")
        return

    if not tts_client:
        logger.warning("[WS /ws/audio] TTS client not available")
        await websocket.close(code=4003, reason="TTS not configured")
        return

    try:
        await websocket.accept()
        logger.info(
            f"[WS /ws/audio] WebSocket connected - session: {sessionId}, project: {project.name}"
        )

        loop = asyncio.get_running_loop()
        ableton_client.set_websocket(websocket, loop)

        # Start sync listeners for real-time parameter updates
        sync_service = get_sync_service(ableton_client)
        project_data = db_service.load_project_structure(projectId)
        if project_data:
            sync_service.start_listeners(projectId, project_data)

        # Set up session
        context.set_session(sessionId, projectId)

        # Create chat session if needed
        session = db_service.get_chat_session(sessionId)
        if not session:
            logger.info(f"[WS /ws/audio] Creating new chat session: {sessionId}")
            db_service.create_chat_session(f"Chat - {project.name}", sessionId)
            db_service.link_session_to_project(sessionId, projectId)

        # Send tracks info to frontend
        await websocket.send_json({"type": "loading_progress", "content": 10})
        tracks_for_frontend = db_service.get_project_tracks_for_frontend(projectId)
        await websocket.send_json({"type": "tracks", "content": tracks_for_frontend})
        await websocket.send_json({"type": "loading_progress", "content": 100})
        logger.info("[WS /ws/audio] WebSocket setup complete")

        # Handle incoming messages
        while True:
            data = await websocket.receive_json()
            msg = data.get("message")
            logger.info(f"[WS /ws/audio] Received WS Data: {data}")

            # Skip blank audio markers - no speech detected
            if msg == "[BLANK_AUDIO]" or not msg or not msg.strip():
                logger.debug("[WS /ws/audio] Skipping blank/empty audio")
                continue

            if msg == "get-param-changes":
                logger.info("[WS /ws/audio] Processing parameter changes request")
                changes_summary = db_service.get_recent_parameter_changes()
                await process_agent_with_tts(
                    websocket,
                    agent,
                    context,
                    {"role": "user", "content": json.dumps(changes_summary)},
                    db_service,
                    ableton_client,
                    tts_client,
                )
                continue

            logger.info(f"[WS /ws/audio] Processing user message: {msg[:100]}...")
            await process_agent_with_tts(
                websocket,
                agent,
                context,
                {"role": "user", "content": msg},
                db_service,
                ableton_client,
                tts_client,
            )

    except WebSocketDisconnect:
        logger.info(f"[WS /ws/audio] WebSocket disconnected for session: {sessionId}")
        sync_service = get_sync_service(ableton_client)
        sync_service.stop_listeners()
        ableton_client.unset_websocket()
    except Exception as e:
        logger.error(
            f"[WS /ws/audio] WebSocket error for session {sessionId}: {str(e)}",
            exc_info=True,
        )
        await websocket.close(code=1011, reason=str(e))
        sync_service = get_sync_service(ableton_client)
        sync_service.stop_listeners()
        ableton_client.unset_websocket()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
