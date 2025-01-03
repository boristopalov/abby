from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Server Configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WEBSOCKET_PORT: int = 8000
    
    # Database Configuration
    DATABASE_URL: str = "sqlite:///./live.db"
    
    # Google AI Configuration
    GOOGLE_API_KEY: str
    
    # Ableton Configuration
    ABLETON_OSC_PORT: int = 11000

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()