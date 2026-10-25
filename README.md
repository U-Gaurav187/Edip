# Edip - Acrobat-Grade Native PDF Engine & Studio

<div align="center">

[![Live Web Studio](https://img.shields.io/badge/Live%20Web%20Studio-edip.run.place-blue?style=for-the-badge&logo=googlechrome&logoColor=white)](https://edip.run.place)
[![Download Android APK](https://img.shields.io/badge/Download%20APK-v1.0.0%20Release-brightgreen?style=for-the-badge&logo=android&logoColor=white)](https://github.com/U-Gaurav187/Edip/releases/latest/download/edip-v1.0.0.apk)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)
[![Security Policy](https://img.shields.io/badge/Security-Policy-red.svg?style=for-the-badge)](SECURITY.md)

### A true in-place PDF editor for Web & Android that edits text, images, and scanned documents without fake white-box overlays or quality loss.

[**Explore Live Web Studio**](https://edip.run.place) • [**Download Android App**](https://github.com/U-Gaurav187/Edip/releases/latest/download/edip-v1.0.0.apk) • [**API Reference**](#-rest-api-reference) • [**Local Setup**](#-running-locally)

</div>

---

## 🎯 What Does Edip Do?

**Edip** is a complete, free, and open-source PDF editing suite that matches Adobe Acrobat Pro's underlying architecture. Most online PDF editors simply draw a white rectangle over the old text and place new text on top. **Edip does real, object-level editing:**

* ✍️ **Edit Text Directly in Any PDF**: Click on any word, number, title, or table cell to edit it in place. Edip automatically identifies and matches the original font family, font size, baseline alignment, and text color.
* 🧼 **Zero Fake White Boxes (No Hidden Text Leaks)**: Unlike typical editors that leave the original private text hidden underneath a white rectangle, Edip surgically eradicates the old character drawing operators from the PDF's internal ISO 32000-1 content stream. The old text is permanently gone, preventing confidential data leaks, copy-paste glitches, and broken search indexing.
* 📷 **Scanned Documents & Photos (Built-in OCR)**: Upload scanned contracts, invoices, or photos. Edip's native C Tesseract engine automatically recognizes the text, generates a clean text layer, and makes every character editable.
* 🎨 **Seamless Background Healing**: When editing text on graphic brochures or scanned paper textures, Edip samples surrounding pixels and seamlessly interpolates the background underneath the modified text while strictly preserving vector line art and illustrations (`PDF_REDACT_LINE_ART_NONE`).
* 🖼️ **Transform & Replace Images**: Move, resize, or replace embedded images directly inside the PDF content stream via transformation matrices (`cm`) without losing resolution or re-encoding other page elements.
* 🔄 **Instant Page Management**: Rotate pages by 90°, delete unwanted pages, or reorder pages in milliseconds.
* 📱 **Native Android Mobile App**: Edit PDFs on the go with a dedicated Android application featuring multi-touch pinch-to-zoom, tap-to-select words, drag-to-nudge spatial positioning, and direct export to WhatsApp, Drive, or Gmail.
* 🌐 **Instant Web Studio**: Use the web editor at [**edip.run.place**](https://edip.run.place) directly from any desktop or mobile browser with zero installation or account sign-ups.

---

## 🌐 Live Deployments & Applications

* **Web Studio**: [https://edip.run.place](https://edip.run.place)
* **Interactive API Documentation (Swagger UI)**: [https://edip.run.place/docs](https://edip.run.place/docs)
* **Android Release APK**: [Download latest `edip-v1.0.0.apk`](https://github.com/U-Gaurav187/Edip/releases/latest/download/edip-v1.0.0.apk)

---

## 🚫 Why Visual Overlay Hacks Are Eradicated

Typical browser-based PDF editors simulate editing using visual hacks:
1. **White rectangles (`re`, `f`)** drawn over the original text to conceal it.
2. **Invisible text layers** positioned on top of flattened images.
3. **Annotation overlays** (`/Annots`) that can be stripped or revealed by standard PDF viewers.

### The Risks of Overlay Hacks:
* **Data Leaks**: The original sensitive text remains inside the PDF content stream underneath the white box, exposing private information.
* **Corrupted Copy-Paste**: Selecting text copies both the old and new text or garbled glyphs.
* **Search Indexing**: Search engines and PDF viewers continue to index the concealed old text.
* **Bloat**: File sizes balloon as pages are converted to heavy flattened bitmaps.

### The Acrobat-Grade Approach in Edip:
* **Surgical Content Stream Eradication**: The engine parses the ISO 32000-1 `/Contents` stream and physically purges target character drawing operators (`Tj`, `TJ`, `BT ... ET`). The old text is permanently eradicated from the file stream.
* **Genuine PDF Object Insertion**: Replacement text is inserted as true PDF drawing operators matching exact font metrics, baseline transformation matrices (`Tm`), and `/ToUnicode` CMaps.
* **Seamless Background Healing & Vector Protection**: For scanned documents or raster brochures, seamless strip interpolation heals the raster background while strictly protecting vector line art and illustrations (`PDF_REDACT_LINE_ART_NONE`).
* **Compaction & Garbage Collection**: Streams are cleaned, deflated, and compacted (`garbage=4`, `deflate=True`), producing clean, lightweight output.

---

## 📱 Edip Android Application (`edip/`)

A high-performance native Android application built with **Kotlin** and **Jetpack Compose**, connecting directly to the live backend API at `https://edip.run.place`.

* **Pinch-to-Zoom & Pan**: Fluid multi-touch gesture canvas enabling microscopic inspection of fine print, complex vector charts, and table rows.
* **Tap-to-Select Text Objects**: Tap any word or line on screen to highlight bounding boxes and open the bottom sheet editor.
* **Spatial Drag-to-Nudge**: Drag text objects visually on screen before committing changes to the backend.
* **Precision Font Controls**: Real-time adjustment of font families (Helvetica, Times, Courier), font size steppers, and color swatches.
* **Page Management**: Instant 90° page rotation, page reordering, and multi-page navigation.
* **Native Storage & Sharing**: Pick any PDF from device storage, edit in real time, and export/share directly to WhatsApp, Gmail, Drive, or local storage.

---

## 🏛 Architecture & Component Diagram

```
┌──────────────────────────────────────┐     ┌──────────────────────────────────────┐
│           Edip Web Studio            │     │          Edip Android App            │
│   (HTML5 Canvas + AST Hotspots)      │     │    (Jetpack Compose + Coil Canvas)   │
└──────────────────┬───────────────────┘     └──────────────────┬───────────────────┘
                   │                                            │
                   │               REST / HTTPS                 │
                   └─────────────────────┬──────────────────────┘
                                         ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│                          FastAPI Core Engine Service                              │
│       /api/documents  │  /api/pages  │  /api/text  │  /api/images  │  /api/ocr    │
└────────────────────────────────────────┬──────────────────────────────────────────┘
                                         │
        ┌────────────────────────────────┼────────────────────────────────┐
        ▼                                ▼                                ▼
┌──────────────────┐           ┌──────────────────┐            ┌──────────────────┐
│   Text Editor    │           │   Image Editor   │            │    OCR Engine    │
│ Surgical glyph   │           │  cm Matrix &     │            │  MuPDF Native    │
│ eradication &    │           │  XObject stream  │            │  Tesseract C-API │
│ clean insertion  │           │  rewriter        │            │  (eng.tessdata)  │
└───────┬──────────┘           └─────────┬────────┘            └────────┬─────────┘
        │                                │                              │
        └────────────────────────────────┼──────────────────────────────┘
                                         ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│                              Artifex MuPDF C-Core                                 │
│         (ISO 32000-1 Page Tree, Object Streams, Font Dictionaries, Inpainting)   │
└───────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📁 Repository Structure

```
PDF EDITOR/
├── app/
│   ├── api/
│   │   ├── documents.py         # Upload, session inspect, export, filename sanitization
│   │   ├── pages.py             # Raster render (PNG/JPEG), rotation, reorder, delete
│   │   ├── text.py              # Surgical text edit, delete, insert
│   │   ├── images.py            # Image transform (cm matrix), replace, delete
│   │   ├── forms.py             # AcroForms field inspection and updates
│   │   ├── annotations.py       # Isolated PDF /Annots management
│   │   └── ocr.py               # Scanned page detection and text layer synthesis
│   ├── core/
│   │   ├── engine.py            # Session manager, in-memory render caching, AST
│   │   ├── text_editor.py       # Operator eradication, font match, seamless inpainting
│   │   ├── image_editor.py      # XObject stream & cm transformation matrix editor
│   │   ├── stream_parser.py     # ISO 32000-1 graphics state tokenizer
│   │   ├── font_manager.py      # Font metric matching and resolution
│   │   ├── page_editor.py       # Page tree manipulation (reorder, duplicate, merge)
│   │   ├── ocr_engine.py        # Native Tesseract OCR text layer builder
│   │   └── exporter.py          # Garbage-collected, deflated PDF/A clean exporter
│   ├── models/                  # Pydantic v2 schemas for requests and AST responses
│   ├── config.py                # Environment configuration (PORT, HOST, CORS)
│   └── main.py                  # FastAPI entrypoint + static Studio mount
├── static/
│   └── index.html               # Web Studio single-page application
├── edip/                        # Native Android Studio project (Jetpack Compose)
│   ├── app/                     # Android app module (UI, ViewModels, Retrofit)
│   ├── build.gradle.kts         # Root and app build configurations
│   └── settings.gradle.kts
├── tessdata/
│   └── eng.traineddata          # Free trained Tesseract model
├── tests/                       # Automated pytest test suites (15 tests, 100% pass)
├── Dockerfile                   # Cloud container definition
├── requirements.txt             # Python dependencies
├── run_server.py                # Server runner
├── .env.example                 # Environment variable template
├── .gitignore                   # Comprehensive git protection rules
├── LICENSE                      # Official MIT Open Source License
└── SECURITY.md                  # Private vulnerability reporting policy
```

---

## 🔌 REST API Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/documents/upload` | Upload PDF or image; initializes an isolated session |
| `GET` | `/api/documents/{id}/pages/{page}/inspect` | Returns full AST (text spans, bounding boxes, images, forms) |
| `GET` | `/api/documents/{id}/pages/{page}/render` | High-fidelity raster render (`dpi`, `format`, `quality`) |
| `POST` | `/api/documents/{id}/text/edit` | Surgical in-place text replacement |
| `POST` | `/api/documents/{id}/text/delete` | Eradicate text span without leaving visual traces |
| `POST` | `/api/documents/{id}/images/{img}/transform` | Move, resize, or rotate image via `cm` matrix |
| `POST` | `/api/documents/{id}/pages/{page}/rotate` | Rotate page in 90° increments |
| `POST` | `/api/documents/{id}/pages/{page}/ocr` | Run C-native OCR and synthesize selectable text |
| `GET` | `/api/documents/{id}/export` | Download clean, deflated, compacted PDF |

---

## 💻 Running Locally

### 1. Backend & Web Studio

```bash
# Clone the repository
git clone https://github.com/U-Gaurav187/Edip.git
cd Edip

# Install dependencies
pip install -r requirements.txt

# Run automated tests
python -m pytest tests -v

# Start the application
python run_server.py
```

Access locally at:
* **Web Studio**: `http://localhost:8000`
* **Swagger API Docs**: `http://localhost:8000/docs`

### 2. Android Mobile Application

1. Open **Android Studio** (Ladybug or later recommended).
2. Select **Open** and choose the `edip/` directory.
3. Allow Gradle to sync dependencies.
4. Select your connected device or emulator and click **Run (▶)**.

---

## ☁️ Free Cloud Deployment

### Deploy with Docker
```bash
docker build -t edip-engine .
docker run -p 8000:8000 edip-engine
```

### Deploy to Render / Hugging Face
1. Create a new Web Service or Space connected to this repository.
2. The bundled `Dockerfile` automatically installs Tesseract C-libraries and configures the environment.
3. Bind `$PORT` and `$HOST` dynamically via environment variables.

---

## 🔒 Security & Vulnerability Reporting

Security and user privacy are strictly prioritized:
* **No hardcoded secrets or API keys**: The engine runs entirely on local/open-source libraries.
* **Safe In-Memory Redactions**: Redactions permanently remove underlying stream operators.
* **Path Traversal Protection**: Upload and export filenames are rigorously sanitized.

To report a vulnerability privately, please review our [Security Policy](SECURITY.md) or email:  
📧 **gauravu2007@gmail.com** (Subject: `[SECURITY] PDF Engine Vulnerability Report`)

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).  
Copyright (c) 2026 Gaurav Upadhyay.
