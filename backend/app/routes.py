import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .ableton import AbletonClient, get_ableton_client
from .db.db_service import DBService, get_db_service
from .logger import logger
from .sync import get_sync_service

router = APIRouter()


class CreateProjectRequest(BaseModel):
    name: str


class ProjectResponse(BaseModel):
    id: int
    name: str
    indexedAt: int


@router.get("/parameter-changes")
async def get_parameter_changes(
    projectId: int,
    since: int = 0,
    db_service: DBService = Depends(get_db_service),
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
        # Verify project exists
        project = db_service.get_project(projectId)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Query DB for changes since timestamp
        changes = db_service.get_parameter_changes_since(projectId, since)
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
def get_sessions(db_service: DBService = Depends(get_db_service)):
    try:
        logger.info("[GET /api/sessions] Fetching all chat sessions")
        sessions = db_service.get_all_chat_sessions()

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
    session_id: str, db_service: DBService = Depends(get_db_service)
):
    try:
        logger.info(
            f"[GET /api/session/{session_id}/messages] Fetching messages for session: {session_id}"
        )
        session = db_service.get_chat_session(session_id)

        if not session:
            logger.warning(
                f"[GET /api/session/{session_id}/messages] Session not found: {session_id}"
            )
            raise HTTPException(status_code=404, detail="Session not found")

        camel_case_messages = [
            {
                snake_to_camel(k): v
                for k, v in message.__dict__.items()
                if not k.startswith("_") and k != "session"
            }
            for message in session.messages
        ]

        logger.info(
            f"[GET /api/session/{session_id}/messages] Successfully fetched messages for session: {session_id}"
        )
        return {"messages": camel_case_messages}
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
def get_projects(db_service: DBService = Depends(get_db_service)):
    """List all projects."""
    try:
        logger.info("[GET /api/projects] Fetching all projects")
        projects = db_service.get_all_projects()

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
    db_service: DBService = Depends(get_db_service),
    ableton_client: AbletonClient = Depends(get_ableton_client),
):
    """Create a new project and index it from Ableton."""
    try:
        logger.info(f"[POST /api/projects] Creating project: {request.name}")

        # Check if project name already exists
        existing = db_service.get_project_by_name(request.name)
        if existing:
            raise HTTPException(
                status_code=400, detail=f"Project '{request.name}' already exists"
            )

        # Check if Ableton is running
        is_live = await ableton_client.is_live()
        if not is_live:
            raise HTTPException(
                status_code=503, detail="Cannot connect to Ableton Live"
            )

        # Create project in DB
        project = db_service.create_project(request.name)
        logger.info(f"[POST /api/projects] Created project with ID: {project.id}")

        # Index project from Ableton
        project_data = await ableton_client.index_project()
        db_service.save_song_context(project.id, project_data["song_context"])
        db_service.save_project_structure(project.id, project_data["tracks"])
        logger.info(
            f"[POST /api/projects] Indexed {len(project_data['tracks'])} tracks for project: {request.name}"
        )

        return {
            "id": project.id,
            "name": project.name,
            "indexedAt": project.indexed_at,
            "trackCount": len(project_data["tracks"]),
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
    db_service: DBService = Depends(get_db_service),
    ableton_client: AbletonClient = Depends(get_ableton_client),
):
    """Delete a project and all its data."""
    try:
        logger.info(f"[DELETE /api/projects/{project_id}] Deleting project")

        project = db_service.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Stop sync listeners if this project is being synced
        sync_service = get_sync_service(ableton_client)
        if sync_service.active_project_id == project_id:
            sync_service.stop_listeners()

        db_service.delete_project(project_id)
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
    db_service: DBService = Depends(get_db_service),
    ableton_client: AbletonClient = Depends(get_ableton_client),
):
    """Re-index an existing project from Ableton."""
    try:
        logger.info(f"[POST /api/projects/{project_id}/reindex] Re-indexing project")

        project = db_service.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Check if Ableton is running
        is_live = await ableton_client.is_live()
        if not is_live:
            raise HTTPException(
                status_code=503, detail="Cannot connect to Ableton Live"
            )

        # Stop existing sync listeners before re-indexing
        sync_service = get_sync_service(ableton_client)
        sync_service.stop_listeners()

        # Clear existing structure and re-index
        db_service.clear_project_structure(project_id)
        project_data = await ableton_client.index_project()
        db_service.save_song_context(project_id, project_data["song_context"])
        db_service.save_project_structure(project_id, project_data["tracks"])
        db_service.update_project_indexed_at(project_id)

        logger.info(
            f"[POST /api/projects/{project_id}/reindex] Re-indexed {len(project_data['tracks'])} tracks"
        )

        # Start sync listeners for the re-indexed project
        sync_service.start_listeners(project_id, project_data["tracks"])

        return {
            "id": project.id,
            "name": project.name,
            "trackCount": len(project_data["tracks"]),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"[POST /api/projects/{project_id}/reindex] Failed: {str(e)}", exc_info=True
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to re-index project: {str(e)}"
        )
