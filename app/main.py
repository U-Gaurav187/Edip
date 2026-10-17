from contextlib import asynccontextmanager
from pathlib import Path
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import pymupdf

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

from .config import settings
from .api.documents import router as documents_router
from .api.pages import router as pages_router
from .api.text import router as text_router
from .api.images import router as images_router
from .api.forms import router as forms_router
from .api.annotations import router as annotations_router
from .api.ocr import router as ocr_router

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure storage and tessdata directories exist
    settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    yield
    # Shutdown: clean up any residual files in session storage
    try:
        for f in settings.STORAGE_DIR.glob("*.pdf"):
            try:
                f.unlink(missing_ok=True)
            except Exception:
                pass
    except Exception:
        pass

app = FastAPI(
    title="Acrobat-Grade Native PDF Engine API",
    description=(
        "Production RESTful PDF Engine for real PDF object manipulation. "
        "Operates directly on PDF objects, content streams, and font dictionaries. "
        "No visual overlay hacks, no white boxes, no hidden text."
    ),
    version="1.0.0",
    lifespan=lifespan
)

# Universal CORS Middleware configured for external clients (Android Studio, web apps, iOS)
origins = settings.CORS_ORIGINS
allow_all = "*" in origins or origins == ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if allow_all else origins,
    allow_credentials=False if allow_all else True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all API routers under /api
app.include_router(documents_router, prefix="/api")
app.include_router(pages_router, prefix="/api")
app.include_router(text_router, prefix="/api")
app.include_router(images_router, prefix="/api")
app.include_router(forms_router, prefix="/api")
app.include_router(annotations_router, prefix="/api")
app.include_router(ocr_router, prefix="/api")

# Mount static files directory if present
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "engine": "Artifex MuPDF",
        "engine_version": pymupdf.version[0],
        "binding_version": pymupdf.VersionBind,
        "ocr_available": (settings.TESSDATA_DIR / "eng.traineddata").exists()
    }

@app.get("/", tags=["UI"])
async def root():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {
        "name": "PDF Engine API",
        "status": "online",
        "docs_url": "/docs",
        "health_url": "/health"
    }
