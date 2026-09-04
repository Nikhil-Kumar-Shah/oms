# Runtime Architecture & System Topology
**Paradox Sports Operations Management System (OMS)**

---

## 1. System Architecture Overview

The Paradox Sports Operations Management System (OMS) utilizes a hardened, decoupled, multi-tier runtime architecture consisting of:
1. **Nginx Reverse Proxy & TLS Termination**: Unified public gateway on ports 80/443.
2. **Next.js Production Frontend**: React 19 / Server-Side Rendering (SSR) & static assets on internal port 3000.
3. **FastAPI Authoritative Backend**: Python 3.12 asynchronous REST API with 4 Uvicorn workers on internal port 8000.
4. **PostgreSQL Database Engine**: ACID-compliant persistent database with connection pooling on internal port 5432.

```
                      [ PUBLIC CLIENTS / BROWSERS ]
                                   │
                           HTTPS (Port 443)
                                   ▼
                 ┌───────────────────────────────────┐
                 │        NGINX REVERSE PROXY        │
                 │      (Rate Limit, TLS, HSTS)      │
                 └─────────────────┬─────────────────┘
                                   │
         ┌─────────────────────────┴─────────────────────────┐
         │                                                   │
  / (Pages & SSR)                                      /api/v1/* (REST API)
  /_next/* (Build Assets)                              /health (Minimal Probe)
         │                                             /ws/* (WebSockets)
         ▼                                                   ▼
┌──────────────────┐                               ┌──────────────────┐
│ NEXT.JS FRONTEND │                               │ FASTAPI BACKEND  │
│  (Node.js v20)   │                               │  (Python 3.12)   │
│  Port 3000 (LAN) │                               │  Port 8000 (LAN) │
└──────────────────┘                               └────────┬─────────┘
                                                            │
                                                     SQLAlchemy 2.0 Pool
                                                            │
                                                            ▼
                                                   ┌──────────────────┐
                                                   │    POSTGRESQL    │
                                                   │    (Port 5432)   │
                                                   │ ACID / Persistent│
                                                   └──────────────────┘
```

---

## 2. Port & Network Boundary Matrix

| Component | Public Exposure | Internal Bind Address | Protocol | Function |
|---|---|---|---|---|
| **Nginx (HTTP)** | **Yes (Port 80)** | `0.0.0.0:80` | HTTP/1.1 | Redirects to HTTPS (Port 443) & ACME challenges |
| **Nginx (HTTPS)** | **Yes (Port 443)** | `0.0.0.0:443` | HTTPS / HTTP2 | SSL/TLS termination, rate limiting, unified routing |
| **Next.js Node Server** | **No (Blocked by UFW)** | `127.0.0.1:3000` | HTTP/1.1 | SSR and frontend React component delivery |
| **FastAPI Uvicorn** | **No (Blocked by UFW)** | `127.0.0.1:8000` | HTTP/1.1 / WS | REST API business logic & database interaction |
| **PostgreSQL** | **No (Blocked by UFW)** | `127.0.0.1:5432` | TCP / PGSQL | Authoritative persistent relational database |

> **Security Rule**: Ports 3000, 8000, and 5432 are strictly bound to `127.0.0.1` and blocked by UFW firewall from external traffic. Normal users only communicate over port 443.

---

## 3. Request Routing & Proxy Strategy

### 3.1 URL Routing Matrix
```
Nginx Ingress
   ├── /                      → Next.js (http://127.0.0.1:3000)
   ├── /_next/static/*        → Next.js (Cached: 1 year immutable)
   ├── /_next/*               → Next.js (http://127.0.0.1:3000)
   ├── /static/*              → Local Disk (/opt/paradox-oms/static/, Cached: 30 days)
   ├── /api/v1/auth/login     → FastAPI (http://127.0.0.1:8000, Rate Limit: 10r/m)
   ├── /api/v1/*              → FastAPI (http://127.0.0.1:8000, Rate Limit: 120r/m)
   ├── /ws/*                  → FastAPI (WebSocket Upgrade)
   ├── /health                → FastAPI (http://127.0.0.1:8000/health)
   └── /dev                   → Nginx 404 Not Found (Disabled in Production)
```

### 3.2 Dynamic Frontend API Resolution
The frontend API client (`frontend/lib/api.ts`) dynamically resolves the backend base URL:
- **Browser Environment**: Resolves to relative path `/api/v1`. All API calls flow through the same HTTPS origin and Nginx reverse proxy.
- **Node.js SSR Environment**: Resolves to direct backend port `http://127.0.0.1:8000/api/v1`.
- **Standalone Development**: Uses `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api/v1`.

---

## 4. Systemd Process Management & Service Hierarchy

```
                      [ multi-user.target ]
                                │
                     [ paradox-oms.target ]
                                │
         ┌──────────────────────┴──────────────────────┐
         ▼                                             ▼
[ paradox-backend.service ]                 [ paradox-frontend.service ]
  - Requires: postgresql.service              - After: paradox-backend.service
  - ExecStart: Uvicorn (4 workers)            - ExecStart: Next.js (Port 3000)
  - User: omsapp:omsapp                       - User: omsapp:omsapp
  - Restart: always (5s delay)                - Restart: always (5s delay)
```

### 4.1 Dependency & Ordering Guarantees
- **PostgreSQL** must start before `paradox-backend.service`.
- **FastAPI Backend** must start before `paradox-frontend.service`.
- **Nginx** forwards to upstream targets and automatically retries upon worker restarts.

---

## 5. Security & Isolation Controls

1. **System Service Isolation**:
   - Dedicated unprivileged system user `omsapp:omsapp`.
   - `ProtectSystem=full`, `ProtectHome=true`, `NoNewPrivileges=true`, `PrivateTmp=true`.
2. **Environment File Security**:
   - `/etc/paradox-oms/production.env` configured with permissions `0600` owned by `omsapp:omsapp`.
3. **Hardened HTTP Headers (Nginx)**:
   - `X-Frame-Options: DENY`
   - `X-Content-Type-Options: nosniff`
   - `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload`
   - `Referrer-Policy: strict-origin-when-cross-origin`
   - `Permissions-Policy: camera=(), microphone=(), geolocation=()`
4. **Endpoint Restrictions**:
   - `/dev` returns `404 Not Found`.
   - `/docs`, `/redoc`, `/openapi.json` are gated with HTTP Basic Authentication or disabled (`ENABLE_DOCS=false`).
   - `/health` exposes only minimal status `{"status": "healthy"}`.
