from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .ableton import AbletonClient, get_ableton_client
from .db.db_service import DBService, get_db_service
from .logger import logger

router = APIRouter()


class GenreRequest(BaseModel):
    genre: str


class CreateProjectRequest(BaseModel):
    name: str


class ProjectResponse(BaseModel):
    id: int
    name: str
    indexedAt: int


class GenreResponse(BaseModel):
    genres: List[str]
    defaultGenre: Optional[str]
    currentGenre: Optional[str]


@router.get("/genres")
def get_genres(db_service: DBService = Depends(get_db_service)) -> GenreResponse:
    try:
        logger.info("[GET /api/genres] Fetching all genres")
        genres = db_service.get_genres()
        default_genre = db_service.get_default_genre()

        response = {
            "genres": [g.name for g in genres],
            "defaultGenre": default_genre.name if default_genre else None,
            "currentGenre": genres[0].name,
        }
        logger.info(f"[GET /api/genres] Successfully fetched genres: {response}")
        return GenreResponse(**response)
    except Exception as e:
        logger.error(
            f"[GET /api/genres] Failed to fetch genres: {str(e)}", exc_info=True
        )
        raise HTTPException(status_code=500, detail="Failed to fetch genres")


@router.post("/genres/set-default")
def set_default_genre(
    genre_req: GenreRequest, db_service: DBService = Depends(get_db_service)
):
    try:
        logger.info(
            f"[POST /api/genres/set-default] Setting default genre to: {genre_req.genre}"
        )
        existing_genre = db_service.get_genre_by_name(genre_req.genre)

        if not existing_genre:
            logger.warning(
                f"[POST /api/genres/set-default] Genre not found: {genre_req.genre}"
            )
            raise HTTPException(status_code=404, detail="Genre not found")

        db_service.set_default_genre(genre_req.genre)
        logger.info(
            f"[POST /api/genres/set-default] Successfully set default genre to: {genre_req.genre}"
        )
        return {"success": True, "genre": genre_req.genre}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(
            f"[POST /api/genres/set-default] Failed to set default genre: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed to set default genre")


@router.get("/parameter-changes")
def get_parameter_changes(db_service: DBService = Depends(get_db_service)):
    try:
        logger.info("[GET /api/parameter-changes] Fetching recent parameter changes")
        changes = db_service.get_recent_parameter_changes()

        if not changes:
            logger.info(
                "[GET /api/parameter-changes] No recent parameter changes found"
            )
            return {"changes": None, "message": None}
        logger.info(
            f"[GET /api/parameter-changes] Successfully fetched {len(changes)} parameter changes"
        )
        return {"changes": changes}
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

        logger.info(f"[GET /api/sessions] Successfully fetched {len(session_list)} sessions")
        return {"sessions": session_list}
    except Exception as e:
        logger.error(
            f"[GET /api/sessions] Failed to fetch sessions: {str(e)}", exc_info=True
        )
        raise HTTPException(status_code=500, detail="Failed to fetch sessions")


# @router.get("/random-genre")
# def get_random_genre(
#     db_service: DBService = Depends(get_db_service), agent=Depends(get_agent)
# ):
#     try:
#         logger.info("[GET /api/random-genre] Generating random genre")
#         genre_name, prompt = agent.generate_random_genre()
#         if not genre_name:
#             logger.error(
#                 "[GET /api/random-genre] Failed to generate genre name - received empty response"
#             )
#             raise HTTPException(status_code=500, detail="Failed to generate genre name")

#         logger.info(
#             f"[GET /api/random-genre] Adding new genre to database: {genre_name}"
#         )
#         db_service.add_genre(genre_name, prompt)

#         logger.info(
#             f"[GET /api/random-genre] Successfully generated and added random genre: {genre_name}"
#         )
#         return {"success": True, "genre": genre_name, "systemPrompt": prompt}
#     except HTTPException as e:
#         raise e
#     except Exception as e:
#         logger.error(
#             f"[GET /api/random-genre] Failed to generate random genre: {str(e)}",
#             exc_info=True,
#         )
#         raise HTTPException(status_code=500, detail="Failed to generate random genre")


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
        tracks_data = await ableton_client.index_project()
        db_service.save_project_structure(project.id, tracks_data)
        logger.info(
            f"[POST /api/projects] Indexed {len(tracks_data)} tracks for project: {request.name}"
        )

        return {
            "id": project.id,
            "name": project.name,
            "indexedAt": project.indexed_at,
            "trackCount": len(tracks_data),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[POST /api/projects] Failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create project: {str(e)}")


@router.delete("/projects/{project_id}")
def delete_project(
    project_id: int, db_service: DBService = Depends(get_db_service)
):
    """Delete a project and all its data."""
    try:
        logger.info(f"[DELETE /api/projects/{project_id}] Deleting project")

        project = db_service.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

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

        # Clear existing structure and re-index
        db_service.clear_project_structure(project_id)
        tracks_data = await ableton_client.index_project()
        db_service.save_project_structure(project_id, tracks_data)
        db_service.update_project_indexed_at(project_id)

        logger.info(
            f"[POST /api/projects/{project_id}/reindex] Re-indexed {len(tracks_data)} tracks"
        )

        return {
            "id": project.id,
            "name": project.name,
            "trackCount": len(tracks_data),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"[POST /api/projects/{project_id}/reindex] Failed: {str(e)}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Failed to re-index project: {str(e)}")
