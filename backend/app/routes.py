from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from .db import get_db
from .db.db_service import DBService
from .chat import get_chat_context
from .agent import get_agent

router = APIRouter()

class GenreRequest(BaseModel):
    genre: str

class GenreResponse(BaseModel):
    genres: List[str]
    defaultGenre: Optional[str]
    currentGenre: Optional[str]

@router.get("/genres")
def get_genres(db: Session = Depends(get_db)) -> GenreResponse:
    try:
        db_service = DBService(db)
        genres = db_service.get_genres()
        default_genre = db_service.get_default_genre()
        context = get_chat_context()
        
        return {
            "genres": [g.name for g in genres],
            "defaultGenre": default_genre.name if default_genre else None,
            "currentGenre": context.current_genre.genre if context.current_genre else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch genres")

@router.post("/genres/set-current")
def set_current_genre(genre_req: GenreRequest, db: Session = Depends(get_db)):
    try:
        db_service = DBService(db)
        existing_genre = db_service.get_genre_by_name(genre_req.genre)
        
        if not existing_genre:
            raise HTTPException(status_code=404, detail="Genre not found")
            
        context = get_chat_context()
        context.set_current_genre(genre_req.genre)
        return {"success": True, "genre": genre_req.genre}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to set current genre")

@router.post("/genres/set-default")
def set_default_genre(genre_req: GenreRequest, db: Session = Depends(get_db)):
    try:
        db_service = DBService(db)
        existing_genre = db_service.get_genre_by_name(genre_req.genre)
        
        if not existing_genre:
            raise HTTPException(status_code=404, detail="Genre not found")
            
        db_service.set_default_genre(genre_req.genre)
        return {"success": True, "genre": genre_req.genre}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to set default genre")

@router.get("/parameter-changes")
def get_parameter_changes(db: Session = Depends(get_db)):
    try:
        db_service = DBService(db)
        changes = db_service.get_recent_parameter_changes()
        
        if not changes:
            return {
                "changes": [],
                "message": "No recent parameter changes found"
            }
        return {"changes": changes}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch parameter changes")

@router.get("/random-genre")
async def get_random_genre(
    db: Session = Depends(get_db),
    agent = Depends(get_agent)
):
    try:
        genre_name, prompt = await agent.generate_random_genre()
        if not genre_name:
            raise HTTPException(status_code=500, detail="Failed to generate genre name")
            
        db_service = DBService(db)
        db_service.add_genre(genre_name, prompt)
        
        return {
            "success": True,
            "genre": genre_name,
            "systemPrompt": prompt
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to generate random genre")

@router.get("/session/{session_id}/messages")
def get_session_messages(session_id: str, db: Session = Depends(get_db)):
    try:
        db_service = DBService(db)
        session = db_service.get_session(session_id)
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
            
        return {"messages": session.messages}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch session messages")
