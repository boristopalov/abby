from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import json
from typing import Optional

from .routes import router as api_router
from .chat import ChatContext, get_chat_context
from .db.db_service import DBService, get_db_service
from .agent import agent
from .ableton import AbletonClient
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

ableton_client = AbletonClient()

@app.get("/")
async def root():
    return {"message": "Ableton Assistant API"}

@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: Optional[str] = None,
    db_service: DBService = Depends(get_db_service),
    context: ChatContext = Depends(get_chat_context)
):
    if not session_id:
        await websocket.close(code=4000, reason="Session ID is required")
        return

    await websocket.accept()

    try:
        # Clear message history if this is a new session
        if session_id != context.current_session_id:
            context.clear_messages()
            context.current_session_id = session_id
            session = db_service.get_chat_session(session_id)
            if not session:
                db_service.create_chat_session("Chat Session 123", session_id)

        ableton_client.set_ws_client(websocket)
        
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
                async for chunk in agent.process_message({
                    "role": "user",
                    "content": json.dumps(changes_summary)
                }, context, db_service, ableton_client):
                    await websocket.send_json(chunk)
                continue

            if data.get("type") == "suggestion_response":
                if data.get("response") == "yes":
                    async for chunk in agent.process_message({
                        "role": "user",
                        "content": "Yes, please make the suggestions you outlined."
                    }, context, db_service, ableton_client):
                        await websocket.send_json(chunk)
                continue

            async for chunk in agent.process_message({
                "role": "user",
                "content": msg
            }, context, db_service, ableton_client):
                await websocket.send_json(chunk)

    except WebSocketDisconnect:
        ableton_client.unset_ws_client()
    except Exception as e:
        print(f"WebSocket error: {str(e)}")
        await websocket.close(code=1011, reason=str(e))
        ableton_client.unset_ws_client()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)