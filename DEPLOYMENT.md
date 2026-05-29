# OmniSource Deployment

## 1. Prepare env

Copy the template and fill real secrets:

```powershell
Copy-Item .env.example .env
```

Important production values:

```env
HTTP_PORT=80
FRONTEND_ORIGIN_REGEX=https://your-flutter-web-domain\.com
AUTH_JWT_ALLOW_EPHEMERAL_KEYS=false
AUTH_JWT_PRIVATE_KEY_PATH=certs/private.pem
AUTH_JWT_PUBLIC_KEY_PATH=certs/public.pem
ML_VECTOR_BACKEND=hash
```

For several frontend domains, use a regex group:

```env
FRONTEND_ORIGIN_REGEX=(https://app\.example\.com|https://www\.example\.com)
```

## 2. Add RSA keys

Put keys into:

```text
server/certs/private.pem
server/certs/public.pem
```

They are mounted into the API container and are excluded from the Docker build
context.

## 3. Build and start

```powershell
docker compose build api
docker compose up -d
docker compose ps
```

Health checks:

```powershell
curl http://localhost/health
curl http://localhost/diagnostics
```

## 4. Semantic vectors

The Docker image bakes the SentenceTransformers model cache during build, so
semantic mode does not download the model at container startup.

The default `ML_VECTOR_BACKEND=hash` matches the current demo database. If you
switch to semantic mode, refresh vectors once:

```powershell
docker compose exec api python run_seed_vectors.py --vectors-only --refresh-all --semantic-vectors
```

Then set:

```env
ML_VECTOR_BACKEND=semantic
```

and redeploy:

```powershell
docker compose up -d --build api
```
