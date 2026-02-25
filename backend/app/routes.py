from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .ableton_client import AbletonClient, get_ableton_client
from .agent import ChatService
from .analytics import AnalyticsService, get_analytics_service
from .db.chat_repository import ChatRepository, get_chat_repository
from .db.project_repository import ProjectRepository, get_project_repository
from .logger import logger

router = APIRouter()


class CreateProjectRequest(BaseModel):
    name: str


class ProjectResponse(BaseModel):
    id: int
    name: str
    indexedAt: int | None


@router.get("/sessions")
def get_sessions(chat_repo: ChatRepository = Depends(get_chat_repository)):
    try:
        logger.info("[GET /api/sessions] Fetching all chat sessions")
        sessions = chat_repo.get_all_chat_sessions()

        session_list = sorted(
            [{"id": s.id, "name": s.name, "createdAt": s.created_at} for s in sessions],
            key=lambda x: x["createdAt"],
            reverse=True,
        )

        logger.info(
            f"[GET /api/sessions] Successfully fetched {len(session_list)} sessions"
        )
        return {"sessions": session_list}
    except Exception as e:
        logger.error(
            f"[GET /api/sessions] Failed to fetch sessions: {str(e)}", exc_info=True
        )
        raise HTTPException(status_code=500, detail="Failed to fetch sessions")


@router.get("/session/{session_id}/messages")
def get_session_messages(
    session_id: str,
    chat_repo: ChatRepository = Depends(get_chat_repository),
    ableton_client: AbletonClient = Depends(get_ableton_client),
):
    try:
        logger.info(
            f"[GET /api/session/{session_id}/messages] Fetching messages for session: {session_id}"
        )
        session = chat_repo.get_chat_session(session_id)

        if not session:
            logger.warning(
                f"[GET /api/session/{session_id}/messages] Session not found: {session_id}"
            )
            raise HTTPException(status_code=404, detail="Session not found")

        chat_service = ChatService(chat_repo, ableton_client)
        messages = chat_service.get_messages_for_display(session_id)

        logger.info(
            f"[GET /api/session/{session_id}/messages] Successfully fetched messages for session: {session_id}"
        )
        return {"messages": messages}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(
            f"[GET /api/session/{session_id}/messages] Failed to fetch session messages: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed to fetch session messages")


def snake_to_camel(snake_str):
    """Converts a snake_case string to camelCase."""
    components = snake_str.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


# Project management routes


@router.get("/projects")
def get_projects(project_repo: ProjectRepository = Depends(get_project_repository)):
    """List all projects."""
    try:
        logger.info("[GET /api/projects] Fetching all projects")
        projects = project_repo.get_all_projects()

        project_list = [{"id": p.id, "name": p.name} for p in projects]

        logger.info(f"[GET /api/projects] Found {len(project_list)} projects")
        return {"projects": project_list}
    except Exception as e:
        logger.error(f"[GET /api/projects] Failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch projects")


@router.post("/projects")
async def create_project(
    request: CreateProjectRequest,
    project_repo: ProjectRepository = Depends(get_project_repository),
    ableton_client: AbletonClient = Depends(get_ableton_client),
    analytics: AnalyticsService = Depends(get_analytics_service),
):
    """Create a new project. Indexing happens in the background when the WebSocket connects."""
    try:
        logger.info(f"[POST /api/projects] Creating project: {request.name}")

        # TODO: no need to throw an error here :D
        existing = project_repo.get_project_by_name(request.name)
        if existing:
            raise HTTPException(
                status_code=400, detail=f"Project '{request.name}' already exists"
            )

        is_live = await ableton_client.is_live()
        if not is_live:
            raise HTTPException(
                status_code=503, detail="Cannot connect to Ableton Live"
            )

        project = project_repo.create_project(request.name)
        logger.info(f"[POST /api/projects] Created project with ID: {project.id}")
        analytics.capture("server", "project_created", {"project_id": project.id})

        return {
            "id": project.id,
            "name": project.name,
            "indexedAt": None,
            "trackCount": 0,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[POST /api/projects] Failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to create project: {str(e)}"
        )


@router.delete("/projects/{project_id}")
def delete_project(
    project_id: int,
    project_repo: ProjectRepository = Depends(get_project_repository),
):
    """Delete a project and all its data."""
    try:
        logger.info(f"[DELETE /api/projects/{project_id}] Deleting project")

        project = project_repo.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        project_repo.delete_project(project_id)
        logger.info(f"[DELETE /api/projects/{project_id}] Project deleted")

        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"[DELETE /api/projects/{project_id}] Failed: {str(e)}", exc_info=True
        )
        raise HTTPException(status_code=500, detail="Failed to delete project")
