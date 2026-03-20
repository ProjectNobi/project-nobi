# 🚀 Project Nobi — Deployment Guide

## Prerequisites

- **Docker** 24+ with Compose v2
- **Git** for code updates
- **Domain** pointed to your server IP (for SSL)
- At least one LLM API key (Chutes.ai or OpenRouter)

## Quick Start (Docker Compose — Recommended)

```bash
# 1. Clone the repo
git clone https://github.com/ProjectNobi/project-nobi.git
cd project-nobi

# 2. Configure environment
cp deploy/.env.example deploy/.env
nano deploy/.env  # Fill in API keys

# 3. Deploy
bash deploy/deploy.sh --env production
```

The stack runs:
- **API** on port 8042 (FastAPI + Gunicorn)
- **Webapp** on port 3000 (Next.js)
- **Nginx** on ports 80/443 (reverse proxy)

## SSL/TLS with Let's Encrypt

```bash
# 1. Create cert directory
mkdir -p deploy/nginx/certs

# 2. Get certificates with certbot
sudo certbot certonly --standalone \
    -d projectnobi.ai \
    -d www.projectnobi.ai

# 3. Copy or symlink certs
ln -s /etc/letsencrypt/live/projectnobi.ai/fullchain.pem deploy/nginx/certs/
ln -s /etc/letsencrypt/live/projectnobi.ai/privkey.pem deploy/nginx/certs/

# 4. Restart nginx
docker compose -f deploy/docker-compose.yml restart nginx
```

**Auto-renewal** (add to crontab):
```
0 3 * * * certbot renew --quiet && docker compose -f /path/to/deploy/docker-compose.yml restart nginx
```

## Manual Setup (systemd — No Docker)

```bash
# 1. Install system deps
sudo apt update && sudo apt install -y python3.12 python3.12-venv nodejs npm nginx

# 2. Create user
sudo useradd -r -m -d /opt/project-nobi nobi

# 3. Clone and setup
sudo -u nobi git clone https://github.com/ProjectNobi/project-nobi.git /opt/project-nobi
cd /opt/project-nobi

# 4. Python venv for API
sudo -u nobi python3.12 -m venv venv
sudo -u nobi venv/bin/pip install -r requirements.txt -r api/requirements.txt gunicorn uvicorn

# 5. Build webapp
cd webapp && sudo -u nobi npm ci && sudo -u nobi npm run build && cd ..

# 6. Install PM2
sudo npm install -g pm2

# 7. Configure env
sudo cp deploy/.env.example deploy/.env
sudo nano deploy/.env

# 8. Install systemd services
sudo cp deploy/systemd/nobi-api.service /etc/systemd/system/
sudo cp deploy/systemd/nobi-webapp.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now nobi-api nobi-webapp
```

## Vercel Deploy (Webapp Only)

For deploying just the frontend to Vercel:

```bash
cd webapp
npx vercel --prod
```

The webapp will use `NEXT_PUBLIC_API_URL` to connect to your API server.

## Managing Services

### Docker Compose
```bash
# View logs
docker compose -f deploy/docker-compose.yml logs -f

# Restart specific service
docker compose -f deploy/docker-compose.yml restart api

# Stop everything
docker compose -f deploy/docker-compose.yml down

# Rebuild and restart
docker compose -f deploy/docker-compose.yml up -d --build
```

### systemd
```bash
# Check status
sudo systemctl status nobi-api nobi-webapp

# View logs
sudo journalctl -u nobi-api -f
sudo journalctl -u nobi-webapp -f

# Restart
sudo systemctl restart nobi-api
```

## Monitoring

### Health Endpoints
- API: `http://localhost:8042/health`
- Webapp: `http://localhost:3000`

### Resource monitoring
```bash
# Docker stats
docker stats nobi-api nobi-webapp nobi-nginx

# Disk usage
docker system df
```

## Backup

### Database backup
```bash
# Docker
docker cp nobi-api:/data/memories.db ./backups/memories-$(date +%Y%m%d).db

# systemd
cp /opt/project-nobi/data/memories.db ./backups/memories-$(date +%Y%m%d).db
```

### Automated backup (crontab)
```
0 2 * * * docker cp nobi-api:/data/memories.db /backups/nobi/memories-$(date +\%Y\%m\%d).db
```

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CHUTES_API_KEY` | Yes* | — | Chutes.ai API key for LLM |
| `OPENROUTER_API_KEY` | Yes* | — | OpenRouter API key (alternative) |
| `CHUTES_MODEL` | No | `deepseek-ai/DeepSeek-V3.1-TEE` | LLM model name |
| `STRIPE_API_KEY` | No | — | Stripe secret key for billing |
| `STRIPE_WEBHOOK_SECRET` | No | — | Stripe webhook signing secret |
| `NOBI_DB_PATH` | No | `~/.nobi/webapp_memories.db` | Memory database path |
| `NOBI_BILLING_DB_PATH` | No | `~/.nobi/billing.db` | Billing database path |
| `NOBI_API_PORT` | No | `8042` | API server port |
| `NEXT_PUBLIC_API_URL` | Yes | — | Public API URL for frontend |

\* At least one LLM provider key is required.

## Troubleshooting

- **API won't start**: Check `CHUTES_API_KEY` or `OPENROUTER_API_KEY` is set
- **Webapp build fails**: Run `npm ci` in `webapp/` first
- **Nginx 502**: Wait for API/webapp health checks to pass
- **SSL errors**: Ensure certs exist at `deploy/nginx/certs/`
