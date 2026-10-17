FROM python:3.12-slim

# Install system dependencies for native MuPDF graphics and font handling
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Hugging Face Spaces security requires running under non-root UID 1000
RUN useradd -m -u 1000 user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=7860

WORKDIR $HOME/app

# Install Python requirements with layer caching
COPY --chown=user:user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY --chown=user:user . .

# Ensure storage directory exists with write permissions for user 1000
RUN mkdir -p /tmp/pdf_editor_sessions && chown -R user:user /tmp/pdf_editor_sessions $HOME/app

USER user

# Hugging Face Spaces routes external traffic to port 7860
EXPOSE 7860

CMD ["python", "run_server.py"]
