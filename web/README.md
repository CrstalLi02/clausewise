# Clausewise Frontend (React + Next.js)

A chat interface built on Next.js 15 (App Router) + React 19 + TypeScript, **fully separated** from the backend (Python FastAPI).

For the complete page workflows for all three roles, permission differences, and explanations of core concepts, see: [Clausewise Frontend User Guide](../design_files/Clausewise-Frontend-User-Guide.md).

## Features

- Login and role-based routing: student accounts → Q&A page; admin accounts → admin console
- Student Q&A: conversational Q&A (`/api/v1/chat`), citation display, department filter, clear conversation, health status
- Admin console (`AdminDashboard`):
  - Overview: Loop progressive-exit progress (human-in-the-loop / on-the-loop / out-of-the-loop) and phase descriptions
  - Department Management · Document Ingestion: create departments, upload documents, visualization of the eight stages of the 3.2 Pipeline
  - Review Center: per-question review judgments, department accuracy, and exit progress
  - Loop Flow · Skill Evolution: five-stage loop, Skills/Hooks/Rules, badcase → rubric rules
    - Manual Loop runs automatically track the asynchronous job and display structured results, instead of only returning a `job_id`
    - Workflow, canary, version, and metric cards for executable baseline Skills + automatically mined Skills
  - Department Sub-Agents: visualization of each agent stack (Orchestrator/Intent/Retrieval/Answer/Verifier)
- `/api/*` is proxied to the Python backend via Next.js rewrites (no extra nginx required)

## Directory Structure

```
web/
├── src/
│   ├── app/                # App Router (layout / page / globals.css)
│   ├── components/         # Login / Chat / AdminDashboard + admin/ panels
│   │   └── admin/          # Overview / Dept / Review / Loop / Insights / Agent
│   └── lib/                # api.ts types and call wrappers (including auth token)
├── scripts/                # Browser smoke tests for the three roles and the Loop page
├── next.config.mjs         # rewrites proxy + standalone output
├── Dockerfile
└── package.json
```

## Running

### Docker (recommended, see the root docker-compose)

Visit http://localhost:8080 (Next.js reverse-proxies `/api` to `backend:8000`).

### Local Development

```bash
cd web
npm install
BACKEND_URL=http://localhost:8000 npm run dev   # http://localhost:3000
```

### Production Build

```bash
npm run build && npm start
```

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `BACKEND_URL` | Python backend URL (rewrites target) | `http://localhost:8000` |
