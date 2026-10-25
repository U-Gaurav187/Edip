# Acrobat-Grade Native PDF Engine & Studio

A production-grade PDF editing engine and web studio built from the ground up to perform **Real PDF Object Editing** matching Adobe Acrobat Pro's underlying architecture.

---

## 🚫 Why Visual Overlay Hacks Are Eradicated

Typical browser-based PDF editors simulate editing using:
1. **White rectangles (`re`, `f`)** drawn over the original text to hide it.
2. **Invisible text layers** placed on top of flattened images.
3. **Annotation overlays** (`/Annots`) that can be deleted or uncovered by standard PDF viewers.

### The Dangers of Overlay Hacks:
- The original sensitive text is still present in the file stream underneath the white box, exposing private data.
- Copy-pasting text copies both the old and new text or garbled glyphs.
- Search indexing continues to find the hidden old text.
- File sizes blow up with redundant raster images.

### The Acrobat-Grade Approach in This Engine:
- **Surgical Content Stream Eradication**: The engine parses the PDF `/Contents` stream and physically removes the target character drawing operators (`Tj`, `TJ`, `BT ... ET`). The old text is purged from the PDF stream entirely.
- **True PDF Object Insertion**: Replacement text is re-inserted as genuine PDF drawing operators using matching font metrics, baseline matrices (`Tm`), and `/ToUnicode` CMaps.
- **Clean Stream Consolidation**: Content streams are compacted and garbage-collected (`garbage=4`, `deflate=True`), leaving no residual artifacts.
- **XObject Image Transformation**: Images are moved, resized, and rotated by updating the Current Transformation Matrix (`cm`) preceding the `/Image Do` operator in the content stream, or replacing the raw XObject stream directly.

---

## 🏛 Architecture & Component Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                   Acrobat Studio Web Interface                  │
│       (Interactive Hotspot Canvas Overlay + Live AST Inspector)  │
└────────────────────────────────┬─────────────────────────────────┘
                                 │ REST / JSON (CORS-enabled)
                                 ▼
┌──────────────────────────────────────────────────────────────────┐
│                    FastAPI REST / Engine API                     │
│  /api/documents  │  /api/pages  │  /api/text  │  /api/images     │
│  /api/forms      │  /api/annots │  /api/ocr   │  /api/export     │
└────────────────────────────────┬─────────────────────────────────┘
                                 │
         ┌───────────────────────┼────────────────────────┐
         ▼                       ▼                        ▼
┌──────────────────┐   ┌──────────────────┐    ┌──────────────────┐
│   Text Editor    │   │   Image Editor   │    │  OCR Engine (C)  │
│  Surgical glyph  │   │   cm Matrix &    │    │  Native MuPDF    │
│  eradication &   │   │   XObject stream │    │  Tesseract       │
│  exact insertion │   │   rewriter       │    │  (eng.tessdata)  │
└────────┬─────────┘   └─────────┬────────┘    └────────┬─────────┘
         │                       │                      │
         └───────────────────────┼──────────────────────┘
                                 ▼
┌──────────────────────────────────────────────────────────────────┐
│                     Artifex MuPDF C-Engine                       │
│    (ISO 32000-1 Page Tree, /Contents Parser, Font Dictionaries)  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 📁 Repository Structure

```
PDF EDITOR/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── documents.py      # Upload, session inspect, export, close
│   │   │   ├── pages.py          # Render (raster PNG), rotate, reorder, delete
│   │   │   ├── text.py           # Surgical text edit, delete, insert
│   │   │   ├── images.py         # Image transform (cm matrix), replace, delete
│   │   │   ├── forms.py          # AcroForms field update and creation
│   │   │   ├── annotations.py    # Isolated PDF /Annots management
│   │   │   └── ocr.py            # Scanned page detection and text layer synthesis
│   │   ├── core/
│   │   │   ├── engine.py         # Session manager, concurrency locks, AST generator
│   │   │   ├── text_editor.py    # Surgical operator eradication & text object writer
│   │   │   ├── image_editor.py   # XObject stream & cm transformation editor
│   │   │   ├── stream_parser.py  # ISO 32000-1 graphics state tokenizer
│   │   │   ├── font_manager.py   # Font resolution, standard 14 matching, embedded fonts
│   │   │   ├── page_editor.py    # Page tree manipulation (reorder, duplicate, merge)
│   │   │   ├── ocr_engine.py     # C-native Tesseract OCR layer builder
│   │   │   ├── form_editor.py    # AcroForm interactive widget manager
│   │   │   ├── annot_editor.py   # Native PDF annotation objects
│   │   │   └── exporter.py       # Garbage-collected, deflated PDF/A / clean exporter
│   │   ├── models/
│   │   │   ├── requests.py       # Pydantic v2 schemas for all operations
│   │   │   └── responses.py      # Pydantic v2 schemas for object AST
│   │   ├── config.py             # Environment configuration (PORT, HOST, CORS)
│   │   └── main.py               # FastAPI entrypoint + static Studio mount
│   ├── static/
│   │   └── index.html            # Acrobat Studio modern web interface
│   ├── tessdata/
│   │   └── eng.traineddata       # Free trained Tesseract model (4 MB)
│   ├── tests/
│   │   ├── test_stream_editing.py
│   │   ├── test_image_editing.py
│   │   ├── test_ocr.py
│   │   └── test_full_pipeline.py
│   ├── Dockerfile                # Cloud-ready container definition
│   ├── requirements.txt
│   └── run_server.py             # Cloud server runner
├── deploy/
│   ├── render.yaml               # 1-click free deploy blueprint on Render
│   └── docker-compose.yml        # Docker compose configuration
└── README.md
```

---

## 🚀 100% Free Cloud Deployment (Zero Credit Card Required)

This project is built using purely open-source components:
- **No paid PDF SDK licenses** (uses Artifex MuPDF C-core via PyMuPDF).
- **No paid OCR APIs** (uses native C Tesseract engine with bundled `eng.traineddata`).
- **No hardcoded localhost**: Reads `$HOST` (default `0.0.0.0`) and `$PORT` dynamically from the environment.
- **CORS enabled**: Can connect to any external web or desktop frontend.

### Option 1: Deploy on Render (Free Web Service)
1. Push this repository to GitHub.
2. In Render dashboard (free account, no credit card needed), click **New +** → **Blueprint** or **Web Service**.
3. Select your repository.
4. Render will automatically read `deploy/render.yaml` and launch the service.
5. Your API and Studio will be live at `https://your-service.onrender.com`.

### Option 2: Deploy on Hugging Face Spaces (Free Docker SDK)
1. Create a new Space on [Hugging Face](https://huggingface.co/spaces).
2. Choose **Docker** as the Space SDK.
3. Upload the repository.
4. Hugging Face builds and hosts the container for free on cloud CPUs.

### Option 3: Deploy on Railway / Fly.io / VPS
Run with Docker:
```bash
docker build -t acrobatic-pdf-engine backend/
docker run -p 8000:8000 acrobatic-pdf-engine
```

---

## 💻 Running Locally

### 1. Install Dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 2. Run Automated Verification Tests
```bash
python -m pytest tests -v
```
All tests verify:
- Complete eradication of old text operators (no white boxes, no hidden text).
- Surgical image XObject replacement and transformation matrix updates.
- OCR text layer synthesis on scanned documents.
- End-to-end upload, edit, raster rendering, and clean PDF export.

### 3. Launch the Server & Studio
```bash
python run_server.py
```
Open your browser to:
- **Web Studio**: `http://localhost:8000`
- **Interactive Swagger API Docs**: `http://localhost:8000/docs`
- **Health Check**: `http://localhost:8000/health`
