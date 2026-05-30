# Lexora Deployment

Lexora is split across two deployments:

- `Railway`: FastAPI backend from the repo root
- `Vercel`: static frontend from the same repo

## Railway

Railway should deploy the backend from the repository root. This repo includes:

- `Dockerfile` for the preferred build path
- `railway.toml` / `railway.json` for start and healthcheck settings
- `nixpacks.toml` as a fallback if Railway tries Nixpacks instead of Docker

Set these Railway variables before deploying:

- `JWT_SECRET_KEY`: required, minimum 32 characters
- `CORS_ORIGINS`: comma-separated frontend origins, for example `https://your-app.vercel.app,http://localhost:3000`
- `DATABASE_URL`: optional; defaults to local SQLite if omitted

Recommended Railway settings:

1. Root directory: repository root
2. Builder: `Dockerfile` if available
3. Start command: leave empty and use repo config

After the first successful deploy, copy the public Railway URL. You will use it in Vercel as `VITE_API_BASE`.

## Vercel

Vercel can now deploy from either:

- the repository root using `/vercel.json`
- the `frontend` directory using `frontend/vercel.json`

Set this Vercel environment variable:

- `VITE_API_BASE`: your Railway backend URL, for example `https://lexora-production.up.railway.app`

The build step generates `frontend/config.js`, which the HTML pages load before `frontend/api.js`.

## Common Failure Points

- Railway build plan fails immediately: confirm the service root is the repo root, not `frontend`
- Railway app crashes on startup: `JWT_SECRET_KEY` is missing or too short
- Frontend loads but API calls fail: `VITE_API_BASE` or `CORS_ORIGINS` is wrong
- Login/upload works locally but not in production: add the deployed Vercel URL to `CORS_ORIGINS`
