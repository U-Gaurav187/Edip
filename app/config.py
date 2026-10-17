import os
from pathlib import Path
import tempfile
from pydantic import BaseModel

class Settings(BaseModel):
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
    
    # CORS settings: allows connecting from any web frontend or specific allowed origins
    CORS_ORIGINS: list[str] = [
        origin.strip() 
        for origin in os.getenv("CORS_ORIGINS", "*").split(",") 
        if origin.strip()
    ]
    
    # Base storage directory for PDF working sessions
    STORAGE_DIR: Path = Path(os.getenv("STORAGE_DIR", Path(tempfile.gettempdir()) / "pdf_editor_sessions"))
    
    # Tessdata directory for MuPDF native C OCR
    TESSDATA_DIR: Path = Path(os.getenv("TESSDATA_PREFIX", Path(__file__).resolve().parent.parent / "tessdata"))
    
    # Maximum upload size: default 100MB
    MAX_UPLOAD_SIZE_BYTES: int = int(os.getenv("MAX_UPLOAD_SIZE_BYTES", str(100 * 1024 * 1024)))
    
    # Session time to live in minutes
    SESSION_TTL_MINUTES: int = int(os.getenv("SESSION_TTL_MINUTES", "120"))

settings = Settings()
settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
