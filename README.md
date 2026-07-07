# OmniSource

OmniSource is a Flutter + FastAPI media discovery app for movies, books, and
music. It combines external content providers into one product flow with search,
library actions, playlists, analytics events, and a practical recommendation
pipeline.

The project was built as a college diploma / portfolio project and was evaluated
at 96/100 by an independent committee. The engineering focus is fullstack/backend
integration rather than presenting the app as a production AI platform.

## Engineering Focus

- Flutter client + FastAPI backend
- Unified content model for movies, books, and music
- TMDB, Spotify, and Google Books integrations
- MongoDB/Beanie data models
- Redis caching for search, home, recommendations, and library data
- RS256 JWT auth with refresh sessions and password reset
- User interactions and analytics events
- Content-based recommendation pipeline
- Docker Compose + Nginx deployment setup
- GitHub Actions CI with backend checks and Flutter checks

## Product Flow

```text
register/login
-> choose interests
-> search movies/books/music
-> open details
-> save favorites/playlists
-> generate recommendations
-> use deep research/discovery
```

## Architecture

```text
Flutter client
  -> FastAPI backend
      -> MongoDB / Beanie
      -> Redis
      -> TMDB
      -> Spotify
      -> Google Books
```

The Flutter app lives in `lib/`. The FastAPI backend lives in `server/app/`.
MongoDB stores users, content metadata, interactions, playlists, password reset
tokens, and refresh sessions. Redis is used as a cache layer for high-traffic API
responses and user-specific data.

## Backend

The backend is organized around routers, services, provider clients, schemas,
models, cache helpers, and recommendation modules.

Main responsibilities:

- Auth: registration, login, access tokens, refresh tokens, refresh-session
  storage, logout/revoke, password reset, and protected routes.
- Providers: TMDB, Spotify, and Google Books API clients.
- Normalization: provider-specific responses are mapped into one
  `UnifiedContent` schema.
- MongoDB: Beanie document models for users, content metadata, interactions,
  playlists, password resets, and refresh sessions.
- Redis: cache-aside storage for hot paths and explicit invalidation for library
  changes.
- Recommendations: content vectors, weighted user interactions, similarity
  scoring, and fallback discovery results.
- Diagnostics: health, diagnostics, and Prometheus-style metrics endpoints.

Important backend folders:

```text
server/app/api/routers/       # FastAPI route modules
server/app/auth/              # JWT, refresh sessions, password reset
server/app/services/          # content, analytics, library, sync services
server/app/integrations/      # external provider clients
server/app/models/            # Beanie document models
server/app/schemas/           # request/response schemas
server/app/ml/                # vectorizer, ranking engine, evaluation helpers
server/app/core/              # config, Redis, database, logging, metrics
```

## Frontend

The frontend is a Flutter app using Cubit/Bloc for state management and Dio for
HTTP communication with the backend.

Implemented client areas:

- Auth flow: login, registration, password reset, token persistence, and session
  restore.
- Onboarding: interest selection used by recommendation/discovery flows.
- Home: content sections and recommendations.
- Search: movie/book/music search with type filters and analytics tracking.
- Library: favorites, playlists, playlist details, and optimistic favorite
  updates.
- Detail screens: content metadata, related content, previews, and dwell-time
  tracking.
- Profile/settings: profile data, logout, diagnostics/debug surfaces, and local
  offline analytics queue visibility.

The API client injects the access token, refreshes expired sessions with the
refresh token, and can route external images through the backend image proxy.

## External Providers

OmniSource integrates three main providers:

- TMDB for movies, movie search, popular/top-rated lists, and trailer metadata.
- Spotify for music search and track metadata.
- Google Books for book search and volume details.

Provider responses are normalized into a shared content shape:

```text
id / external_id
type: movie | music | book
title
subtitle
description
image_url
rating
genres
release_date
preview_url / external_url
```

The backend handles partial provider failures by returning empty result sets,
logging degradation, retrying selected transient failures, and falling back to
discovery or demo-safe music entries when a provider returns no useful music
results.

## Recommendation Pipeline

The recommendation system is a content-based hybrid ranking pipeline over user
interactions.

It uses:

- weighted implicit events such as views, detail opens, dwell time, preview
  plays, external opens, likes, and playlist additions;
- content vectors stored in MongoDB metadata documents;
- hash embeddings by default for fast and stable local/demo runs;
- optional SentenceTransformers embeddings for semantic vectors;
- cosine similarity between user/profile vectors and content vectors;
- rating, genre, and provider/content-type blending;
- fallback discovery APIs when there is not enough vectorized data.

This is not a trained neural recommender yet. It is a practical ranking pipeline:
content is vectorized, user behavior is aggregated into a weighted profile, and
candidate content is ranked by similarity plus quality and diversity signals.

## Redis / Caching

Redis is used to reduce repeated provider calls and protect external API quotas.

Cached areas include:

- search results;
- home feed sections;
- discovery results;
- general recommendations;
- user-specific recommendations;
- favorites;
- playlist details;
- deep research results.

The Redis wrapper is designed to fail softly: when Redis is disabled or
temporarily unavailable, the backend falls back to MongoDB or provider calls
instead of making the whole API unavailable. Image proxy caching is handled
in-process with TTL, byte limits, host allowlisting, and in-flight request
deduplication.

## Deployment

The repository includes a Docker Compose deployment setup with:

- FastAPI backend container;
- MongoDB;
- Redis;
- Nginx reverse proxy;
- mounted frontend web build directory;
- healthchecks and persistent volumes.

The project has been deployed on a VPS-style environment using Docker Compose
and Nginx. Deployment documentation intentionally keeps hostnames, IP addresses,
SSH users, and secrets out of the repository.

Useful files:

```text
docker-compose.yml
server/Dockerfile
nginx/templates/omnisource.conf.template
DEPLOYMENT.md
.github/workflows/ci.yml
.github/workflows/deploy.yml
```

## Quality Gates

Backend checks:

```bash
cd server
uv run ruff check .
uv run bandit -q -r app -ll
uv run pip-audit --ignore-vuln CVE-2024-23342
uv run pytest -q
```

Current backend status:

- `ruff` passes
- `bandit` passes
- `pip-audit` passes with the documented temporary ignore
- `pytest` passes: 182 backend tests

Flutter checks are configured in CI:

```bash
flutter analyze
flutter test
```

CI runs backend quality gates and Flutter checks through GitHub Actions.

## Local Development

Backend:

```bash
cd server
uv sync
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Flutter web:

```bash
flutter pub get
flutter run -d chrome --dart-define=API_BASE_URL=http://127.0.0.1:8000
```

Docker:

```bash
cp .env.example .env
docker compose up --build
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

## Current Status

Implemented:

- FastAPI backend
- Flutter app
- auth and password reset
- external provider integrations
- MongoDB/Beanie persistence
- Redis caching
- recommendation pipeline
- analytics event tracking
- Docker Compose deployment setup
- Nginx reverse proxy setup
- GitHub Actions CI

Known limitations:

- recommendation logic is not a trained ML model;
- no ANN/vector database yet;
- no full end-to-end browser/API test suite;
- auth rate limiting is local/in-memory, not Redis-distributed;
- no production-grade monitoring/alerting stack;
- external API behavior depends on provider availability, quotas, and regional
  network access.

## Roadmap

v0.2:

- Redis-backed rate limiting
- provider mocks / contract tests
- better content deduplication and data quality rules
- deployed smoke checks after release

v0.3:

- background queue for vector precompute
- vector DB or ANN index for larger catalogs
- offline evaluation dataset
- recommendation model/version tracking

## What This Project Is Not

- Not a production AI platform
- Not a trained ML recommender
- Not a large-scale vector search system
- Not a microservice architecture
- Not a production-hardened security setup

