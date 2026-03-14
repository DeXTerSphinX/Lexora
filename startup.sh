#!/bin/bash
# Download spaCy model if not already present
python -m spacy download en_core_web_md --quiet 2>/dev/null || true
# Download NLTK wordnet data
python -c "import nltk; nltk.download('wordnet', quiet=True)" 2>/dev/null || true
# Start the app on Azure's expected port (default 8000)
gunicorn api.app:app --workers 1 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000} --timeout 120
