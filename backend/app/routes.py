from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from .db import get_db
from .db.db_service import DBService, get_db_service
from .chat import get_chat_context
from .agent import get_agent
from .logger import logger

router = APIRouter()

class GenreRequest(BaseModel):
    genre: str

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
        context = get_chat_context()
        
        response = {
            "genres": [g.name for g in genres],
            "defaultGenre": default_genre.name if default_genre else None,
            "currentGenre": context.current_genre['genre'] if context.current_genre else None
        }
        logger.info(f"[GET /api/genres] Successfully fetched genres: {response}")
        return response
    except Exception as e:
        logger.error(f"[GET /api/genres] Failed to fetch genres: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch genres")

@router.post("/genres/set-current")
def set_current_genre(genre_req: GenreRequest, db_service: DBService = Depends(get_db_service)):
    try:
        logger.info(f"[POST /api/genres/set-current] Setting current genre to: {genre_req.genre}")
        existing_genre = db_service.get_genre_by_name(genre_req.genre)
        
        if not existing_genre:
            logger.warning(f"[POST /api/genres/set-current] Genre not found: {genre_req.genre}")
            raise HTTPException(status_code=404, detail="Genre not found")
            
        context = get_chat_context()
        context.set_current_genre(existing_genre.name, existing_genre.system_prompt)
        logger.info(f"[POST /api/genres/set-current] Successfully set current genre to: {genre_req.genre}")
        return {"success": True, "genre": genre_req.genre}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"[POST /api/genres/set-current] Failed to set current genre: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to set current genre")

@router.post("/genres/set-default")
def set_default_genre(genre_req: GenreRequest, db_service: DBService = Depends(get_db_service)):
    try:
        logger.info(f"[POST /api/genres/set-default] Setting default genre to: {genre_req.genre}")
        existing_genre = db_service.get_genre_by_name(genre_req.genre)
        
        if not existing_genre:
            logger.warning(f"[POST /api/genres/set-default] Genre not found: {genre_req.genre}")
            raise HTTPException(status_code=404, detail="Genre not found")
            
        db_service.set_default_genre(genre_req.genre)
        logger.info(f"[POST /api/genres/set-default] Successfully set default genre to: {genre_req.genre}")
        return {"success": True, "genre": genre_req.genre}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"[POST /api/genres/set-default] Failed to set default genre: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to set default genre")

@router.get("/parameter-changes")
def get_parameter_changes(db_service: Session = Depends(get_db_service)):
    try:
        logger.info("[GET /api/parameter-changes] Fetching recent parameter changes")
        changes = db_service.get_recent_parameter_changes()
        
        if not changes:
            logger.info("[GET /api/parameter-changes] No recent parameter changes found")
            return {
                "changes": [],
                "message": "No recent parameter changes found"
            }
        logger.info(f"[GET /api/parameter-changes] Successfully fetched {len(changes)} parameter changes")
        return {"changes": changes}
    except Exception as e:
        logger.error(f"[GET /api/parameter-changes] Failed to fetch parameter changes: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch parameter changes")

@router.get("/random-genre")
async def get_random_genre(
    db_service: DBService = Depends(get_db_service),
    agent = Depends(get_agent)
):
    try:
        logger.info("[GET /api/random-genre] Generating random genre")
        genre_name, prompt = await agent.generate_random_genre()
        if not genre_name:
            logger.error("[GET /api/random-genre] Failed to generate genre name - received empty response")
            raise HTTPException(status_code=500, detail="Failed to generate genre name")
            
        logger.info(f"[GET /api/random-genre] Adding new genre to database: {genre_name}")
        db_service.add_genre(genre_name, prompt)
        
        logger.info(f"[GET /api/random-genre] Successfully generated and added random genre: {genre_name}")
        return {
            "success": True,
            "genre": genre_name,
            "systemPrompt": prompt
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"[GET /api/random-genre] Failed to generate random genre: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate random genre")

@router.get("/session/{session_id}/messages")
def get_session_messages(session_id: str, db_service: DBService = Depends(get_db_service)):
    try:
        logger.info(f"[GET /api/session/{session_id}/messages] Fetching messages for session: {session_id}")
        session = db_service.get_chat_session(session_id)
        
        if not session:
            logger.warning(f"[GET /api/session/{session_id}/messages] Session not found: {session_id}")
            raise HTTPException(status_code=404, detail="Session not found")
            
        camel_case_messages = [
            {snake_to_camel(k): v for k, v in message.__dict__.items() 
             if not k.startswith('_') and k != 'session'}
            for message in session.messages
        ]

        logger.info(f"[GET /api/session/{session_id}/messages] Successfully fetched messages for session: {session_id}")
        return {"messages": camel_case_messages}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"[GET /api/session/{session_id}/messages] Failed to fetch session messages: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch session messages")


def snake_to_camel(snake_str):
    """Converts a snake_case string to camelCase."""
    components = snake_str.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])
