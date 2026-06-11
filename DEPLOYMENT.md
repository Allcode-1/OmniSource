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
curl http://localhost/api/health
curl http://localhost/api/diagnostics
```

## 4. CI/CD

GitHub Actions has two workflows:

1. `.github/workflows/ci.yml` runs checks and tests.
2. `.github/workflows/deploy.yml` deploys after CI passes on `main`/`master`, or manually from the GitHub Actions tab.

Add these repository secrets in GitHub:

```text
DEPLOY_HOST=5.42.108.117
DEPLOY_USER=<ssh user>
DEPLOY_SSH_KEY=<private ssh key for that user>
```

Optional secrets:

```text
DEPLOY_PORT=22
DEPLOY_PATH=/opt/omnisource
API_BASE_URL=http://5.42.108.117/api
```

The server user must be able to:

1. SSH into the host.
2. Write to `/opt/omnisource` or the custom `DEPLOY_PATH`.
3. Write to `/var/www/omnisource/web`.
4. Run `docker compose`.
5. Run `rsync`.

The deploy workflow keeps production-only files on the server:

1. Root `.env`
2. `server/.env`
3. `server/certs/`

Manual server redeploy, if needed:

```bash
cd /opt/omnisource
docker compose up -d --build api nginx
docker compose ps
curl http://127.0.0.1/api/health
```

## 5. Semantic vectors

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
