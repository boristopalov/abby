import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .ableton_client import AbletonClient, get_ableton_client
from .agent import ChatService
from .analytics import AnalyticsService, get_analytics_service
from .db.ableton_repository import AbletonRepository, get_ableton_repository
from .db.chat_repository import ChatRepository, get_chat_repository
from .db.project_repository import ProjectRepository, get_project_repository
from .logger import logger
from .sync import get_sync_service

router = APIRouter()


class CreateProjectRequest(BaseModel):
    name: str


class ProjectResponse(BaseModel):
    id: int
    name: str
    indexedAt: int | None


@router.get("/parameter-changes")
async def get_parameter_changes(
    projectId: int,
    since: int = 0,
    project_repo: ProjectRepository = Depends(get_project_repository),
    ableton_repo: AbletonRepository = Depends(get_ableton_repository),
):
    """Get parameter changes for a project since a given timestamp.

    Args:
        projectId: The project ID
        since: Unix timestamp in milliseconds. Returns changes after this time.
               Default 0 returns all changes.

    Returns:
        {"changes": [...], "timestamp": current_timestamp}
        The returned timestamp can be used as 'since' in the next request.
    """
    try:
        project = project_repo.get_project(projectId)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # comment out for now
        # changes = ableton_repo.get_parameter_changes_since(projectId, since)
        changes = []
        current_timestamp = int(time.time() * 1000)

        if not changes:
            logger.debug("[GET /api/parameter-changes] No parameter changes found")
            return {"changes": [], "timestamp": current_timestamp}

        logger.info(
            f"[GET /api/parameter-changes] Found {len(changes)} parameter changes"
        )
        return {"changes": changes, "timestamp": current_timestamp}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"[GET /api/parameter-changes] Failed to fetch parameter changes: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed to fetch parameter changes")


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
    ableton_repo: AbletonRepository = Depends(get_ableton_repository),
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

        chat_service = ChatService(chat_repo, ableton_repo, ableton_client)
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

        project_list = [
            {"id": p.id, "name": p.name, "indexedAt": p.indexed_at} for p in projects
        ]

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
    ableton_client: AbletonClient = Depends(get_ableton_client),
):
    """Delete a project and all its data."""
    try:
        logger.info(f"[DELETE /api/projects/{project_id}] Deleting project")

        project = project_repo.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        sync_service = get_sync_service(ableton_client)
        if sync_service.active_project_id == project_id:
            sync_service.stop_listeners()

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


@router.post("/projects/{project_id}/reindex")
async def reindex_project(
    project_id: int,
    project_repo: ProjectRepository = Depends(get_project_repository),
    ableton_repo: AbletonRepository = Depends(get_ableton_repository),
    ableton_client: AbletonClient = Depends(get_ableton_client),
):
    """Trigger re-indexing for an existing project. Indexing happens in the background when the WebSocket reconnects."""
    try:
        logger.info(f"[POST /api/projects/{project_id}/reindex] Triggering re-index")

        project = project_repo.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        is_live = await ableton_client.is_live()
        if not is_live:
            raise HTTPException(
                status_code=503, detail="Cannot connect to Ableton Live"
            )

        sync_service = get_sync_service(ableton_client)
        sync_service.stop_listeners()

        ableton_repo.clear_project_structure(project_id)
        project_repo.clear_project_indexed_at(project_id)

        logger.info(
            f"[POST /api/projects/{project_id}/reindex] Cleared structure, awaiting WebSocket reconnect"
        )

        return {
            "id": project.id,
            "name": project.name,
            "trackCount": 0,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"[POST /api/projects/{project_id}/reindex] Failed: {str(e)}", exc_info=True
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to trigger re-index: {str(e)}"
        )
