# Security Guide

## Overview

This document covers security considerations for deploying the MARP Guide RAG Chatbot, especially for production environments.

## Development vs Production

### Development (Current Setup)
- ✅ Default credentials (guest/guest) for RabbitMQ
- ✅ No authentication on Qdrant
- ✅ Services communicate over internal Docker network
- ⚠️ **NOT suitable for production or public deployment**

### Production Requirements
- 🔒 Custom RabbitMQ credentials
- 🔒 Qdrant authentication enabled
- 🔒 API rate limiting
- 🔒 HTTPS/TLS encryption
- 🔒 Network isolation
- 🔒 Secrets management

---

## RabbitMQ Security

### Current Setup (Development)
```env
RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/
```

### Production Setup

#### 1. Create Custom User in docker-compose.yml

```yaml
rabbitmq:
  image: rabbitmq:3-management
  environment:
    - RABBITMQ_DEFAULT_USER=marp_user
    - RABBITMQ_DEFAULT_PASS=${RABBITMQ_PASSWORD}  # Load from .env
  env_file:
    - .env
```

#### 2. Update .env

```env
# Production RabbitMQ credentials
RABBITMQ_USER=marp_user
RABBITMQ_PASSWORD=your_secure_password_here
RABBITMQ_URL=amqp://marp_user:${RABBITMQ_PASSWORD}@rabbitmq:5672/
```

#### 3. Generate Strong Password

```bash
# Linux/Mac
openssl rand -base64 32

# Windows PowerShell
[Convert]::ToBase64String((1..32 | ForEach-Object { Get-Random -Minimum 0 -Maximum 256 }))
```

#### 4. Disable Guest User (Optional)

Add to RabbitMQ configuration:
```yaml
rabbitmq:
  environment:
    - RABBITMQ_DEFAULT_USER=marp_user
    - RABBITMQ_DEFAULT_PASS=${RABBITMQ_PASSWORD}
  volumes:
    - ./rabbitmq.conf:/etc/rabbitmq/rabbitmq.conf
```

`rabbitmq.conf`:
```
loopback_users.guest = false
```

**Resources:**
- [RabbitMQ Access Control](https://www.rabbitmq.com/access-control.html)
- [RabbitMQ Production Checklist](https://www.rabbitmq.com/production-checklist.html)

---

## Qdrant Security

### Current Setup (Development)
```yaml
qdrant:
  image: qdrant/qdrant:latest
  ports:
    - "6333:6333"
```
⚠️ No authentication - anyone with network access can read/write vectors

### Production Setup

#### 1. Enable API Key Authentication

Update docker-compose.yml:
```yaml
qdrant:
  image: qdrant/qdrant:latest
  environment:
    - QDRANT__SERVICE__API_KEY=${QDRANT_API_KEY}
  env_file:
    - .env
  ports:
    - "6333:6333"
```

#### 2. Update .env

```env
# Production Qdrant API key
QDRANT_API_KEY=your_secure_api_key_here
```

#### 3. Update Services to Use API Key

**services/indexing/app/qdrant_store.py:**
```python
import os
from qdrant_client import QdrantClient

QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

def get_qdrant_client():
    return QdrantClient(
        host=os.getenv("QDRANT_HOST", "localhost"),
        port=int(os.getenv("QDRANT_PORT", 6333)),
        api_key=QDRANT_API_KEY,
        https=os.getenv("QDRANT_USE_HTTPS", "false").lower() == "true"
    )
```

**services/retrieval/app/retriever.py:**
```python
from qdrant_client import QdrantClient

self.client = QdrantClient(
    host=self.qdrant_host,
    port=self.qdrant_port,
    api_key=os.getenv("QDRANT_API_KEY")
)
```

#### 4. Enable HTTPS (Production)

```env
QDRANT_HOST=qdrant.yourdomain.com
QDRANT_PORT=443
QDRANT_USE_HTTPS=true
QDRANT_API_KEY=your_secure_api_key
```

**Resources:**
- [Qdrant Security](https://qdrant.tech/documentation/guides/security/)
- [Qdrant Authentication](https://qdrant.tech/documentation/guides/security/#authentication)

---

## OpenRouter API Key

### Current Risk
Your API key is visible in `.env` file:
```env
OPENROUTER_API_KEY=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
```

### Best Practices

#### 1. Never Commit API Keys
✅ `.env` is in `.gitignore` - good!
❌ Don't paste keys in issues, PRs, or screenshots

#### 2. Use Environment Variables in CI/CD
```yaml
# GitHub Actions example
- name: Deploy
  env:
    OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
```

#### 3. Rotate Keys Regularly
- OpenRouter dashboard → Settings → API Keys
- Revoke old keys after rotation

#### 4. Set Usage Limits
- Configure spending limits in OpenRouter dashboard
- Enable rate limiting to prevent abuse

---

## Docker Network Security

### Current Setup
All services communicate over `app-network` bridge network.

### Production Recommendations

#### 1. Use Internal Networks

```yaml
networks:
  frontend:  # Public-facing services (chat)
    driver: bridge
  backend:   # Internal services only
    driver: bridge
    internal: true  # No external access

services:
  chat:
    networks:
      - frontend
      - backend

  rabbitmq:
    networks:
      - backend  # Not accessible from outside

  qdrant:
    networks:
      - backend  # Not accessible from outside
```

#### 2. Remove Unnecessary Port Exposures

Development:
```yaml
rabbitmq:
  ports:
    - "5672:5672"
    - "15672:15672"
```

Production:
```yaml
rabbitmq:
  # No ports exposed - only accessible within Docker network
```

---

## HTTPS/TLS Encryption

### For Production Deployment

#### 1. Use Reverse Proxy (Nginx/Traefik)

```yaml
nginx:
  image: nginx:alpine
  ports:
    - "443:443"
  volumes:
    - ./nginx.conf:/etc/nginx/nginx.conf
    - ./ssl:/etc/nginx/ssl
  depends_on:
    - chat
```

#### 2. Configure SSL/TLS

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    location / {
        proxy_pass http://chat:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

#### 3. Use Let's Encrypt
```bash
certbot --nginx -d your-domain.com
```

---

## Secrets Management

### Option 1: Docker Secrets (Swarm/Compose)

```yaml
services:
  chat:
    secrets:
      - openrouter_key
      - rabbitmq_password
    environment:
      - OPENROUTER_API_KEY_FILE=/run/secrets/openrouter_key

secrets:
  openrouter_key:
    file: ./secrets/openrouter_key.txt
  rabbitmq_password:
    file: ./secrets/rabbitmq_password.txt
```

### Option 2: External Secret Managers

- **AWS Secrets Manager**
- **Azure Key Vault**
- **HashiCorp Vault**
- **Google Secret Manager**

---

## Security Checklist

### Before Production Deployment

- [ ] Change RabbitMQ default credentials
- [ ] Enable Qdrant API key authentication
- [ ] Rotate OpenRouter API key
- [ ] Remove unnecessary port exposures
- [ ] Configure internal Docker networks
- [ ] Set up HTTPS/TLS with valid certificates
- [ ] Enable rate limiting on public endpoints
- [ ] Configure firewall rules
- [ ] Set up monitoring and alerting
- [ ] Review and minimize service permissions
- [ ] Enable Docker security options (read-only filesystems, no-new-privileges)
- [ ] Regular security updates for all images
- [ ] Implement backup strategy for Qdrant data

### Regular Maintenance

- [ ] Rotate credentials every 90 days
- [ ] Review access logs monthly
- [ ] Update dependencies weekly
- [ ] Security audit quarterly
- [ ] Test disaster recovery procedures

---

## Quick Production Setup

### 1. Generate Secrets

```bash
# Generate RabbitMQ password
RABBITMQ_PASSWORD=$(openssl rand -base64 32)

# Generate Qdrant API key
QDRANT_API_KEY=$(openssl rand -base64 32)
```

### 2. Update .env

```env
# RabbitMQ
RABBITMQ_USER=marp_prod
RABBITMQ_PASSWORD=<generated_password>
RABBITMQ_URL=amqp://marp_prod:${RABBITMQ_PASSWORD}@rabbitmq:5672/

# Qdrant
QDRANT_API_KEY=<generated_key>

# OpenRouter (your existing key)
OPENROUTER_API_KEY=<your_key>
```

### 3. Update docker-compose.yml

```yaml
rabbitmq:
  environment:
    - RABBITMQ_DEFAULT_USER=${RABBITMQ_USER}
    - RABBITMQ_DEFAULT_PASS=${RABBITMQ_PASSWORD}

qdrant:
  environment:
    - QDRANT__SERVICE__API_KEY=${QDRANT_API_KEY}
```

### 4. Update Application Code

Add API key support to Qdrant clients (see code examples above).

---

## Summary

**Current Setup:** ✅ Safe for local development
**For Production:** 🔒 Follow this guide to secure all services
**Priority Order:**
1. Change RabbitMQ credentials (High)
2. Enable Qdrant authentication (High)
3. Setup HTTPS/TLS (Medium)
4. Configure internal networks (Medium)
5. Implement secrets management (Low, but recommended)

**Need Help?** Check the official documentation:
- [Docker Security](https://docs.docker.com/engine/security/)
- [RabbitMQ Security](https://www.rabbitmq.com/security.html)
- [Qdrant Security](https://qdrant.tech/documentation/guides/security/)
