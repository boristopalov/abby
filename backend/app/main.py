from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
import json
from typing import Optional
import traceback

from .routes import router as api_router
from .chat import get_chat_context, ChatContext
from .db.db_service import DBService, get_db_service
from .agent import get_agent, Agent
from .ableton import AbletonClient, get_ableton_client
from dotenv import load_dotenv

load_dotenv()

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
    return {"message": "Ableton Assistant API"}

@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    sessionId: Optional[str] = None,
    db_service: DBService = Depends(get_db_service),
    ableton_client: AbletonClient = Depends(get_ableton_client),
    agent: Agent = Depends(get_agent),
    context: ChatContext = Depends(get_chat_context)
):
    if not sessionId:
        await websocket.close(code=4000, reason="Session ID is required")
        return

    await websocket.accept()

    try:
        # Clear message history if this is a new session
        if sessionId != context.current_session_id:
            context.clear_messages()
            context.current_session_id = sessionId
            session = db_service.get_chat_session(sessionId)
            if not session:
                db_service.create_chat_session("Chat Session 123", sessionId)

        ableton_client.set_websocket(websocket)
        
        if not context.handlers_initialized and not context.handlers_loading:
            context.handlers_loading = True
            await ableton_client.subscribe_to_device_parameters()
            context.handlers_initialized = True
            context.handlers_loading = False
            print("Finished setting up handlers for new session!")
        elif context.handlers_initialized:
            await websocket.send_json({
                "type": "loading_progress",
                "content": 100
            })
            print("Reusing existing parameter subscriptions")

        # Handle incoming messages
        while True:
            data = await websocket.receive_json()
            msg = data.get("message")

            if msg == "get-param-changes":
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
                continue

            if data.get("type") == "suggestion_response":
                if data.get("response") == "yes":
                    async for chunk in agent.process_message(
                        context,
                        {
                            "role": "user",
                            "content": "Yes, please make the suggestions you outlined."
                        },
                        db_service,
                        ableton_client
                    ):
                        await websocket.send_json(chunk)
                continue

            async for chunk in agent.process_message(
                context,
                {
                    "role": "user",
                    "content": msg
                },
                db_service,
                ableton_client
            ):
                await websocket.send_json(chunk)

    except WebSocketDisconnect:
        ableton_client.unset_websocket()
    except Exception as e:
        print(f"WebSocket error: {str(e)}")
        traceback.print_exc()
        await websocket.close(code=1011, reason=str(e))
        ableton_client.unset_websocket()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)