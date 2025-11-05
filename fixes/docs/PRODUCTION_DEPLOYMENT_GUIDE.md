# Production Deployment Guide - Gmail Unsubscriber

## Executive Summary

This guide provides step-by-step instructions for deploying the Gmail Unsubscriber application to production with comprehensive security, monitoring, and reliability features.

**Deployment Time**: ~4 hours (including setup and testing)
**Prerequisites**: Docker, domain name, SSL certificates, cloud provider account
**Recommended Infrastructure**: 2 vCPUs, 4GB RAM, 20GB SSD

---

## Table of Contents

1. [Pre-Deployment Checklist](#pre-deployment-checklist)
2. [Infrastructure Setup](#infrastructure-setup)
3. [Configuration](#configuration)
4. [Deployment Steps](#deployment-steps)
5. [Post-Deployment Verification](#post-deployment-verification)
6. [Monitoring & Maintenance](#monitoring--maintenance)
7. [Troubleshooting](#troubleshooting)
8. [Rollback Procedures](#rollback-procedures)

---

## Pre-Deployment Checklist

### Required Accounts & Services

- [ ] **Google Cloud Console** - OAuth credentials configured
- [ ] **Cloud Provider** - AWS/GCP/Azure/Railway/Heroku account
- [ ] **Domain Name** - Registered and DNS configured
- [ ] **SSL Certificates** - Let's Encrypt or commercial cert
- [ ] **Sentry Account** (recommended) - Error tracking
- [ ] **Redis Instance** - Either self-hosted or managed (ElastiCache, Redis Cloud)
- [ ] **PostgreSQL Database** (recommended) - Either self-hosted or managed (RDS, Cloud SQL)

### Security Requirements

- [ ] Strong SECRET_KEY generated (min 32 bytes)
- [ ] Unique JWT_SECRET_KEY generated
- [ ] Google OAuth credentials obtained
- [ ] Database password set (strong, random)
- [ ] Redis password set (strong, random)
- [ ] Firewall rules configured
- [ ] SSL/TLS certificates installed
- [ ] CORS origins restricted to production domains

### Google OAuth Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable Gmail API
4. Create OAuth 2.0 credentials:
   - Application type: Web application
   - Authorized redirect URIs: `https://your-domain.com/oauth2callback`
5. Save Client ID and Client Secret

---

## Infrastructure Setup

### Option 1: Docker Compose (Recommended for getting started)

#### 1.1 Clone Repository

```bash
git clone https://github.com/your-org/gmailunsubscriber.git
cd gmailunsubscriber
```

#### 1.2 Copy Configuration Files

```bash
# Copy environment template
cp fixes/deployment/.env.example .env

# Generate secrets
python3 -c "import secrets; print(f'SECRET_KEY={secrets.token_hex(32)}')" >> .env
python3 -c "import secrets; print(f'JWT_SECRET_KEY={secrets.token_hex(32)}')" >> .env
python3 -c "import secrets; print(f'REDIS_PASSWORD={secrets.token_hex(16)}')" >> .env
python3 -c "import secrets; print(f'DATABASE_PASSWORD={secrets.token_hex(16)}')" >> .env
```

#### 1.3 Configure Environment Variables

Edit `.env` and fill in:

```bash
# Application
ENVIRONMENT=production
DEBUG=false

# Google OAuth (from Google Cloud Console)
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_PROJECT_ID=your-project-id

# URLs (replace with your actual domain)
REDIRECT_URI=https://your-domain.com/oauth2callback
FRONTEND_URL=https://your-frontend-domain.com

# Security (already generated above)
SECRET_KEY=<generated-above>
JWT_SECRET_KEY=<generated-above>
REDIS_PASSWORD=<generated-above>
DATABASE_PASSWORD=<generated-above>

# Optional: Error tracking
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id

# Optional: Claude AI features
ANTHROPIC_API_KEY=sk-ant-your-api-key
```

#### 1.4 Start Services

```bash
# Start core services
docker-compose -f fixes/deployment/docker-compose.yml up -d

# Start with monitoring (optional)
docker-compose -f fixes/deployment/docker-compose.yml --profile monitoring up -d

# Start with Celery workers (optional)
docker-compose -f fixes/deployment/docker-compose.yml --profile celery up -d

# View logs
docker-compose -f fixes/deployment/docker-compose.yml logs -f
```

#### 1.5 Verify Services

```bash
# Check service health
docker-compose -f fixes/deployment/docker-compose.yml ps

# Test endpoints
curl https://your-domain.com/
curl https://your-domain.com/api/health
```

---

### Option 2: Railway Deployment

#### 2.1 Install Railway CLI

```bash
npm install -g @railway/cli
railway login
```

#### 2.2 Create Project

```bash
railway init
railway link
```

#### 2.3 Add Services

```bash
# Add PostgreSQL
railway add --database postgres

# Add Redis
railway add --database redis
```

#### 2.4 Set Environment Variables

```bash
# Set all required variables
railway variables set SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
railway variables set GOOGLE_CLIENT_ID=your-client-id
railway variables set GOOGLE_CLIENT_SECRET=your-secret
railway variables set GOOGLE_PROJECT_ID=your-project
railway variables set REDIRECT_URI=https://your-app.railway.app/oauth2callback
railway variables set FRONTEND_URL=https://your-frontend.railway.app
railway variables set ENVIRONMENT=production
railway variables set RATELIMIT_ENABLED=true
railway variables set CSP_ENABLED=true
railway variables set HSTS_ENABLED=true

# Railway automatically provides DATABASE_URL and REDIS_URL
```

#### 2.5 Deploy

```bash
railway up
railway open
```

---

### Option 3: AWS Deployment (ECS + RDS + ElastiCache)

#### 3.1 Create RDS PostgreSQL Instance

```bash
aws rds create-db-instance \
  --db-instance-identifier gmail-unsub-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --engine-version 15.4 \
  --master-username admin \
  --master-user-password <strong-password> \
  --allocated-storage 20 \
  --vpc-security-group-ids sg-xxxxx \
  --db-subnet-group-name my-subnet-group
```

#### 3.2 Create ElastiCache Redis Cluster

```bash
aws elasticache create-cache-cluster \
  --cache-cluster-id gmail-unsub-redis \
  --cache-node-type cache.t3.micro \
  --engine redis \
  --engine-version 7.0 \
  --num-cache-nodes 1 \
  --security-group-ids sg-xxxxx
```

#### 3.3 Build and Push Docker Image

```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Build image
docker build -f fixes/deployment/Dockerfile -t gmail-unsub:latest .

# Tag and push
docker tag gmail-unsub:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/gmail-unsub:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/gmail-unsub:latest
```

#### 3.4 Create ECS Task Definition

```bash
aws ecs register-task-definition --cli-input-json file://ecs-task-definition.json
```

#### 3.5 Create ECS Service

```bash
aws ecs create-service \
  --cluster gmail-unsub-cluster \
  --service-name gmail-unsub-service \
  --task-definition gmail-unsub:1 \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxxxx],securityGroups=[sg-xxxxx],assignPublicIp=ENABLED}" \
  --load-balancers "targetGroupArn=arn:aws:elasticloadbalancing:...,containerName=gmail-unsub,containerPort=5000"
```

---

## Configuration

### Security Headers Configuration

The application automatically sets the following security headers in production:

```python
# Content Security Policy
Content-Security-Policy: default-src 'self'; script-src 'self' https://cdnjs.cloudflare.com; ...

# HTTP Strict Transport Security
Strict-Transport-Security: max-age=31536000; includeSubDomains

# X-Frame-Options
X-Frame-Options: DENY

# X-Content-Type-Options
X-Content-Type-Options: nosniff

# Referrer-Policy
Referrer-Policy: strict-origin-when-cross-origin
```

### Rate Limiting Configuration

Default rate limits (configured in `fixes/security/middleware.py`):

- **Authentication**: 5 requests/minute per IP
- **OAuth callback**: 10 requests/hour per IP
- **API endpoints**: 100 requests/hour per user
- **Preview/Apply**: 10 requests/hour per user
- **Global default**: 1000 requests/day per IP

### Database Configuration

#### PostgreSQL (Recommended for production)

```bash
# Connection string format
DATABASE_URL=postgresql://user:password@host:5432/database

# Connection pool settings
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20
DATABASE_POOL_TIMEOUT=30
```

#### SQLite (Development only)

```bash
DATABASE_PATH=gmail_unsubscriber.db
```

### Redis Configuration

```bash
# Connection string
REDIS_URL=redis://:password@host:6379/0

# Redis is used for:
# - Rate limiting (DB 1)
# - Session caching (DB 0)
# - Celery broker (DB 2)
# - Celery results (DB 3)
```

---

## Deployment Steps

### Step 1: Pre-flight Checks

```bash
# Run security scan
cd gmail-unsubscriber-backend
pip install bandit safety
bandit -r . -f json -o bandit-report.json
safety check

# Run tests
pip install pytest pytest-cov
pytest tests/ --cov=. --cov-report=term-missing

# Check configuration
python3 -c "from fixes.security.config import get_config; config = get_config(); config.validate(); print('✓ Configuration valid')"
```

### Step 2: Build Application

```bash
# Build Docker image
docker build -f fixes/deployment/Dockerfile -t gmail-unsub:$(git rev-parse --short HEAD) .

# Tag as latest
docker tag gmail-unsub:$(git rev-parse --short HEAD) gmail-unsub:latest
```

### Step 3: Database Migration

```bash
# Initialize database (first deployment)
docker-compose -f fixes/deployment/docker-compose.yml run backend python -c "
from database import initialize_database
initialize_database()
"

# For future migrations, use Alembic
docker-compose -f fixes/deployment/docker-compose.yml run backend alembic upgrade head
```

### Step 4: Deploy Application

```bash
# Deploy with docker-compose
docker-compose -f fixes/deployment/docker-compose.yml up -d

# OR deploy to cloud provider (see provider-specific instructions above)
```

### Step 5: Configure Nginx/Load Balancer

Create `nginx/conf.d/gmail-unsub.conf`:

```nginx
upstream backend {
    least_conn;
    server backend:5000 max_fails=3 fail_timeout=30s;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    location / {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;

        # Rate limiting
        limit_req zone=api_limit burst=20 nodelay;
    }
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}
```

---

## Post-Deployment Verification

### Automated Verification Script

```bash
#!/bin/bash
# Save as verify-deployment.sh

BASE_URL="https://your-domain.com"

echo "🔍 Verifying deployment..."

# Test 1: Health check
echo "✓ Testing health endpoint..."
curl -f $BASE_URL/ || exit 1

# Test 2: API endpoint
echo "✓ Testing API health..."
curl -f $BASE_URL/api/health || exit 1

# Test 3: Security headers
echo "✓ Checking security headers..."
curl -I $BASE_URL | grep -i "strict-transport-security" || echo "⚠️  HSTS header missing"
curl -I $BASE_URL | grep -i "x-frame-options" || echo "⚠️  X-Frame-Options missing"

# Test 4: SSL certificate
echo "✓ Verifying SSL..."
curl --insecure -vvI $BASE_URL 2>&1 | grep "SSL certificate verify ok" || echo "⚠️  SSL issues detected"

# Test 5: Rate limiting
echo "✓ Testing rate limiting..."
for i in {1..10}; do
    curl -s -o /dev/null -w "%{http_code}\n" $BASE_URL/api/stats
done

# Test 6: OAuth flow (manual verification required)
echo "🔐 Manual verification needed:"
echo "   1. Visit $BASE_URL and click 'Sign in with Google'"
echo "   2. Complete OAuth flow"
echo "   3. Verify dashboard loads"

echo "✅ Automated checks complete!"
```

### Manual Verification Checklist

- [ ] Homepage loads correctly
- [ ] OAuth login flow works
- [ ] Dashboard displays after login
- [ ] Preview functionality works
- [ ] Apply actions works
- [ ] Undo functionality works
- [ ] Logout works
- [ ] HTTPS redirect works
- [ ] Security headers present
- [ ] Rate limiting active
- [ ] Error tracking (Sentry) receiving events
- [ ] Logs are structured (JSON format)
- [ ] Metrics endpoint accessible (Prometheus)

---

## Monitoring & Maintenance

### Prometheus Metrics

The application exposes metrics at `/metrics`:

```
# Request metrics
http_request_duration_seconds
http_requests_total

# Application metrics
gmail_api_calls_total
unsubscribe_actions_total
active_users_gauge
```

### Sentry Error Tracking

Configure Sentry DSN in environment:

```bash
SENTRY_DSN=https://your-key@sentry.io/project-id
```

Sentry will automatically capture:
- Unhandled exceptions
- Failed API calls
- Authentication errors
- Database errors

### Log Aggregation

Logs are output in JSON format for easy parsing:

```json
{
  "timestamp": "2025-11-05T10:30:00Z",
  "level": "INFO",
  "logger": "app",
  "message": "User authenticated",
  "user_id": "user@example.com",
  "request_id": "abc123",
  "duration_ms": 150
}
```

Use log aggregation tools:
- **ELK Stack**: Elasticsearch + Logstash + Kibana
- **Grafana Loki**: Lightweight log aggregation
- **CloudWatch Logs**: AWS native
- **Stackdriver**: GCP native

### Database Backups

#### Automated Backup Script

```bash
#!/bin/bash
# Save as backup-database.sh

BACKUP_DIR="/var/backups/gmail-unsub"
DATE=$(date +%Y%m%d_%H%M%S)
DATABASE_URL="postgresql://user:pass@localhost:5432/gmail_unsub"

mkdir -p $BACKUP_DIR

# Create backup
pg_dump $DATABASE_URL | gzip > $BACKUP_DIR/backup_$DATE.sql.gz

# Rotate old backups (keep last 30 days)
find $BACKUP_DIR -name "backup_*.sql.gz" -mtime +30 -delete

echo "Backup complete: $BACKUP_DIR/backup_$DATE.sql.gz"
```

Schedule with cron:

```cron
# Daily backup at 2 AM
0 2 * * * /path/to/backup-database.sh
```

### Health Check Monitoring

Set up uptime monitoring with:
- **UptimeRobot**: Free tier for basic monitoring
- **Pingdom**: Advanced monitoring
- **AWS CloudWatch**: Native AWS monitoring
- **Custom script**: Check `/api/health` every 5 minutes

---

## Troubleshooting

### Common Issues

#### Issue 1: OAuth State Errors

**Symptoms**: "no_stored_state" error during login

**Solutions**:
1. Ensure Redis is running and accessible
2. Check REDIS_URL is correct
3. Verify session cookies are being set (check browser dev tools)
4. Check CORS configuration allows credentials
5. Verify REDIRECT_URI matches Google Console exactly

#### Issue 2: Rate Limit Exceeded

**Symptoms**: 429 Too Many Requests

**Solutions**:
1. Check Redis is working (rate limit storage)
2. Verify IP address detection is correct
3. Adjust rate limits in `fixes/security/middleware.py`
4. Check for bot traffic

#### Issue 3: Database Connection Errors

**Symptoms**: "could not connect to server"

**Solutions**:
1. Verify DATABASE_URL is correct
2. Check database server is running
3. Verify network connectivity
4. Check firewall rules
5. Verify database credentials

#### Issue 4: High Memory Usage

**Symptoms**: Container OOM kills

**Solutions**:
1. Reduce Gunicorn workers
2. Implement request size limits
3. Enable Redis for session caching
4. Check for memory leaks in application logs

### Debug Mode

Enable verbose logging:

```bash
LOG_LEVEL=DEBUG docker-compose restart backend
docker-compose logs -f backend
```

### Database Console

```bash
# PostgreSQL
docker-compose exec postgres psql -U gmail_user gmail_unsubscriber

# Redis
docker-compose exec redis redis-cli -a <password>
```

---

## Rollback Procedures

### Quick Rollback (Docker)

```bash
# Stop current deployment
docker-compose -f fixes/deployment/docker-compose.yml down

# Restore previous version
docker-compose -f fixes/deployment/docker-compose.yml up -d --force-recreate
```

### Database Rollback

```bash
# Restore from backup
gunzip -c /var/backups/gmail-unsub/backup_YYYYMMDD_HHMMSS.sql.gz | \
  psql postgresql://user:pass@localhost:5432/gmail_unsub
```

### Zero-Downtime Rollback (Blue-Green)

```bash
# Switch traffic back to blue environment
# (Implementation depends on load balancer configuration)
aws elbv2 modify-listener --listener-arn <arn> --default-actions Type=forward,TargetGroupArn=<blue-target-group>
```

---

## Appendix

### A. Complete Environment Variables Reference

See `fixes/deployment/.env.example` for the complete list.

### B. Security Hardening Checklist

- [ ] Secrets rotated every 90 days
- [ ] Database backups verified weekly
- [ ] Security patches applied monthly
- [ ] Access logs reviewed weekly
- [ ] Failed authentication attempts monitored
- [ ] Dependency vulnerabilities scanned weekly
- [ ] Penetration testing performed annually
- [ ] Incident response plan documented
- [ ] Disaster recovery plan tested quarterly

### C. Performance Tuning

```python
# Gunicorn workers calculation
workers = (2 * CPU_cores) + 1

# Database connection pool
pool_size = (Gunicorn_workers * 2) + 5
```

### D. Support & Resources

- **Documentation**: `/fixes/docs/`
- **Security Issues**: Report to security@your-domain.com
- **GitHub Issues**: https://github.com/your-org/gmailunsubscriber/issues

---

**Deployment Date**: _______________
**Deployed By**: _______________
**Sign-off**: _______________

**Next Review Date**: _______________
