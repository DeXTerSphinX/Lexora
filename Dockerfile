FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download spaCy model and NLTK data
RUN python -m spacy download en_core_web_md
RUN python -c "import nltk; nltk.download('wordnet')"

# Copy application code
COPY core/ core/
COPY api/ api/

# Railway sets PORT env var
ENV PORT=8000

EXPOSE ${PORT}

CMD gunicorn api.app:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT} --timeout 120
