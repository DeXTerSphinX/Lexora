FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    tesseract-ocr \
    libtesseract-dev \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN python -m spacy download en_core_web_md
RUN python -c "import nltk; nltk.download('wordnet')"

COPY core/ core/
COPY api/ api/

ENV PORT=8000

EXPOSE ${PORT}

CMD gunicorn api.app:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT} --timeout 120