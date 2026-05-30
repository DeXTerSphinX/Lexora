<div align="center">

```
██╗     ███████╗██╗  ██╗ ██████╗ ██████╗  █████╗ 
██║     ██╔════╝╚██╗██╔╝██╔═══██╗██╔══██╗██╔══██╗
██║     █████╗   ╚███╔╝ ██║   ██║██████╔╝███████║
██║     ██╔══╝   ██╔██╗ ██║   ██║██╔══██╗██╔══██║
███████╗███████╗██╔╝ ██╗╚██████╔╝██║  ██║██║  ██║
╚══════╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝
```

**Cognitive Load Transformation Engine**  
*Making exam papers dyslexia-friendly through NLP-driven structural rewriting*

[![Live Demo](https://img.shields.io/badge/Live%20Demo-lexora--gamma--eight.vercel.app-orange?style=for-the-badge&logo=vercel)](https://lexora-gamma-eight.vercel.app)
[![API](https://img.shields.io/badge/API-lexora--rocg.onrender.com-blue?style=for-the-badge&logo=fastapi)](https://lexora-rocg.onrender.com/health)
[![Python](https://img.shields.io/badge/Python-3.11-yellow?style=for-the-badge&logo=python)](https://python.org)
[![spaCy](https://img.shields.io/badge/spaCy-3.8-09a3d5?style=for-the-badge)](https://spacy.io)

</div>

---

## What It Does

Lexora ingests exam PDFs and rewrites them for dyslexic students — not by simplifying content, but by restructuring syntax. The reading level stays the same. The cognitive load drops.

A question like:

> *"The treaty, which was signed in 1842 and which many historians consider a turning point, was opposed by the faction that had long controlled the northern territories."*

becomes:

> *"The treaty was signed in 1842. Many historians consider it a turning point. A faction had long controlled the northern territories. This faction opposed the treaty."*

Same information. Less working memory required.

---

## Pipeline

```
PDF Upload
    │
    ▼
OCR & Extraction          ← pdfplumber + pytesseract (300 DPI, PSM 6)
    │                        confidence filtering, paragraph restoration
    ▼
Question Parsing          ← regex-based boundary detection
    │                        supports Q.N., N., N) formats
    ▼
Complexity Scoring        ← 4-metric composite score (research-backed)
    │                        sentence length · dependency depth
    │                        lexical difficulty (wordfreq Zipf) · word length
    ▼
Structural Transformation ← 3 spaCy-driven rewrite strategies
    │                        passive→active · appositive separation
    │                        center-embedded clause splitting
    │                        conservative fallback (0.85 confidence threshold)
    ▼
Dyslexia-Friendly Output  ← OpenDyslexic font · keyword highlighting
                             increased line spacing · chunked layout
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | FastAPI + Gunicorn + Uvicorn |
| **NLP** | spaCy `en_core_web_md`, NLTK WordNet, pyinflect |
| **Lexical Analysis** | wordfreq (Zipf frequency scoring) |
| **PDF Ingestion** | pdfplumber + pytesseract (Tesseract OCR) |
| **Auth** | JWT (python-jose) + bcrypt password hashing |
| **Database** | SQLAlchemy + SQLite |
| **Frontend** | Vanilla HTML/CSS/JS (no framework) |
| **Deployment** | Render (backend) + Vercel (frontend) |

---

## Complexity Scoring

Each question gets a composite cognitive load score across four axes:

```python
score = (
    sentence_length_score   # normalized against calibrated bounds [5.9, 28.0]
  + dependency_depth_score  # parse tree depth [2.0, 8.0]
  + lexical_difficulty      # Zipf frequency inverse [2.30, 3.60]
  + word_length_score       # avg chars per token [3.0, 8.0]
)
```

Risk bands: `LOW < 0.6` · `MODERATE 0.6–0.9` · `HIGH 0.9–1.3` · `VERY HIGH > 1.3`

Only questions above threshold are rewritten. Questions already at low complexity pass through unchanged.

---

## Transformation Strategies

**1. Passive → Active**  
Identifies passive constructions via spaCy dependency labels (`nsubjpass`, `auxpass`), recovers the agent from `by`-phrases, and reconstructs active voice using `pyinflect` for correct verb inflection.

**2. Appositive Separation**  
Detects appositive noun phrases (dependency label `appos`) and splits them into separate sentences, eliminating the embedded clause that forces backtracking.

**3. Center-Embedded Clause Splitting**  
Finds relative clauses and subordinate connectives (`because`, `although`, `therefore`) that interrupt the main clause, and restructures them into sequential sentences.

All strategies apply a **0.85 confidence threshold** — if the parse looks uncertain, the original text is returned unchanged.

---

## Auth & API

```
POST /auth/register     Create account (student or admin role)
POST /auth/login        Returns JWT access token (15 min) + refresh token (7 days)
POST /auth/refresh      Rotate tokens
POST /papers/upload     Upload PDF → triggers full pipeline
GET  /papers/{id}       Retrieve transformed output
GET  /health            Service health check
```

JWT tokens stored in `localStorage`. Role-based routing — admin gets the portal, student gets the pre-exam dashboard.

---

## Local Setup

```bash
git clone https://github.com/DeXTerSphinX/Lexora.git
cd Lexora

pip install -r requirements.txt
python -m spacy download en_core_web_md
python -c "import nltk; nltk.download('wordnet')"

# create .env
echo "JWT_SECRET_KEY=your-secret-here" > .env
echo "DATABASE_URL=sqlite:///./lexora.db" >> .env
echo "CORS_ORIGINS=http://localhost:3000" >> .env

uvicorn api.app:app --reload
# frontend: open frontend/Login.html via Live Server
```

---

## Deployment

| Service | Platform | URL |
|---|---|---|
| Backend (FastAPI) | Render (Docker) | `https://lexora-rocg.onrender.com` |
| Frontend (Static) | Vercel | `https://lexora-gamma-eight.vercel.app` |

Required environment variables on Render:
```
JWT_SECRET_KEY
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
CORS_ORIGINS=https://lexora-gamma-eight.vercel.app
DATABASE_URL=sqlite:///./lexora.db
```

Frontend reads `VITE_API_BASE` at build time via `frontend/inject-config.js`.

---

## Known Limitations

- Reading passage paragraph splitting is imperfect for scanned PDFs with non-standard layouts — accepted, not fixing
- Free tier Render instance (512MB RAM) constrains processing to ~10 page PDFs before memory pressure
- SQLite on Render is ephemeral — data resets on redeploy (acceptable for demo; swap `DATABASE_URL` for Postgres in production)

---

## Project Context

Built as a portfolio project during B.Tech CSE (AI & ML) — Amity University, Madhya Pradesh.  
Motivated by accessibility research showing dyslexic students score significantly lower on exams due to sentence complexity, not knowledge gaps.

The long-term vision is a B2B API for coaching institutes (Allen, FIITJEE, etc.) to run accessibility transforms on their existing question banks at upload time.

---

<div align="center">

*Built with Python, spaCy, and a genuine belief that exams should test knowledge — not reading endurance.*

</div>