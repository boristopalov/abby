import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
import json
from typing import Optional

from .db.models import init_db

from .routes import router as api_router
from .chat import get_chat_context, ChatContext
from .db.db_service import DBService, get_db_service
from .agent import get_agent, Agent
from .ableton import AbletonClient, get_ableton_client
from .logger import logger
from dotenv import load_dotenv

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
    resetProject: Optional[bool] = False,
    db_service: DBService = Depends(get_db_service),
    ableton_client: AbletonClient = Depends(get_ableton_client),
    agent: Agent = Depends(get_agent),
    context: ChatContext = Depends(get_chat_context)
):
    if not sessionId:
        logger.warning("[WS /ws] WebSocket connection attempt without session ID")
        await websocket.close(code=4000, reason="Session ID is required")
        return

    if resetProject:
        logger.info(f"[WS /ws] Resetting project for session: {sessionId}")
        context.reset_session()
        ableton_client.parameter_metadata = {}

    try:
        await websocket.accept()
        logger.info(f"[WS /ws] WebSocket connection established for session: {sessionId}")
        
        # Clear message history if this is a new session
        if sessionId != context.current_session_id:
            logger.info(f"[WS /ws] New session started: {sessionId}")
            context.clear_messages()
            context.current_session_id = sessionId
            session = db_service.get_chat_session(sessionId)
            if not session:
                logger.info(f"[WS /ws] Creating new chat session: {sessionId}")
                db_service.create_chat_session("Chat Session 123", sessionId)

        loop = asyncio.get_running_loop()
        ableton_client.set_websocket(websocket, loop)
        
        if not context.handlers_initialized and not context.handlers_loading:
            logger.info("[WS /ws] Initializing parameter handlers for new session")
            context.handlers_loading = True
            await ableton_client.subscribe_to_device_parameters()
            context.handlers_initialized = True
            context.handlers_loading = False
            logger.info("[WS /ws] Successfully set up handlers for new session")
        elif context.handlers_initialized:
            await websocket.send_json({
                "type": "loading_progress",
                "content": 100
            })
            logger.info("[WS /ws] Reusing existing parameter subscriptions")

        # Handle incoming messages
        while True:
            data = await websocket.receive_json()
            msg = data.get("message")

            if msg == "get-param-changes":
                logger.info("[WS /ws] Processing parameter changes request")
                changes_summary = ableton_client.get_recent_parameter_changes()
                async for chunk in agent.process_message(
                    context,
                    {
                        "role": "user",
                        "content": json.dumps(changes_summary)
                    },
                    db_service,
                    ableton_client
                ):
                    await websocket.send_json(chunk)
                    await asyncio.sleep(0)  # Give the event loop a chance to send the message
                continue

            if data.get("type") == "suggestion_response":
                if data.get("response") == "yes":
                    logger.info("[WS /ws] Processing suggestion confirmation")
                    async for chunk in agent.process_message(
                        context,
                        {
                            "role": "user",
                            "content": "Yes, please make the suggestions you outlined."
                        },
                        db_service,
                        ableton_client
                    ):
                        logger.info(f"[WS /ws] Message response: {chunk}")
                        await websocket.send_json(chunk)
                        await asyncio.sleep(0)  # Give the event loop a chance to send the message
                continue

            logger.info(f"[WS /ws] Processing user message: {msg[:100]}...")  # Log first 100 chars of message
            async for chunk in agent.process_message(
                context,
                {
                    "role": "user",
                    "content": msg
                },
                db_service,
                ableton_client
            ):
                logger.info(f"[WS /ws] Sending chunk: {chunk}")
                await websocket.send_json(chunk)
                await asyncio.sleep(0)  # Give the event loop a chance to send the message

    except WebSocketDisconnect:
        logger.info(f"[WS /ws] WebSocket disconnected for session: {sessionId}")
        ableton_client.unset_websocket()
    except Exception as e:
        logger.error(f"[WS /ws] WebSocket error for session {sessionId}: {str(e)}", exc_info=True)
        await websocket.close(code=1011, reason=str(e))
        ableton_client.unset_websocket()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)