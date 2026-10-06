# Clausewise pi Agent Runtime

A unified probabilistic agent execution engine built on [pi](https://github.com/earendil-works/pi) (`@earendil-works/pi-agent-core` + `@earendil-works/pi-ai`).

> Python remains the sole control plane; the pi Runtime only executes agent requests that have passed Python's permission, fact, memory, and policy governance.

## Responsibilities

| Service | Responsibility |
|---|---|
| **pi Runtime (this service)** | Agent loop, model calls, structured output, and controlled tool calling for Intent / Rewrite / Answer / Verify / Reflect |
| **Python control plane** | Authentication, fixed DAG, fact retrieval, memory governance, department isolation, dynamic policies, canary, release, and rollback |

The pi service uses `fetch` to call the Python backend's **internal endpoints** (`/api/v1/internal/*`) to fetch data, run retrieval, and write feedback and Loop outputs.

## Directory Structure

```
services/pi-agent/
├── src/
│   ├── config.ts        # Environment config
│   ├── providers.ts     # pi-ai providers (DeepSeek / relay service, OpenAI-compatible)
│   ├── runtime.ts       # Runtime wiring (model + streamFn + tools)
│   ├── tools.ts         # AgentTool toolset (retrieval / calendar / departments / glossary / feedback / artifact saving)
│   ├── agents.ts        # Agent definitions + runAgent runner + prompts
│   ├── orchestrator.ts  # Intent→Rewrite→Retrieve→Answer→Verify DAG
│   ├── loop.ts          # Loop engine (Observe→Reflect→Adapt)
│   ├── server.ts        # Fastify HTTP server
│   ├── doctor.ts        # pi-side self-check
│   └── index.ts         # Entry point
├── Dockerfile
└── package.json
```

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness check |
| POST | `/v1/agent/run` | Unified agent execution protocol, requires `X-Internal-Token` |
| POST | `/answer` | Q&A (pi orchestrates the full DAG) |
| POST | `/loop/run` | Compatibility pi-internal Loop (not the production web path) |

`/answer` and `/loop/run` are compatibility endpoints that also require the internal token; the production path uses `/v1/agent/run`.

## Running Locally

```bash
cd services/pi-agent
npm install
npm run doctor       # Verify that pi + DeepSeek work
npm run dev          # tsx watch dev mode (:8100)
npm run build && npm start   # Production mode
```

## Environment Variables

See [`.env.example`](./.env.example). Key ones: `DEEPSEEK_API_KEY`, `BACKEND_URL` (Python backend URL).

## Key Design

1. **pi agent loop + tool calling**: agents such as Intent/Answer are pi `Agent` instances, and the model decides on its own which tools to call
   (`list_departments` / `get_glossary` / `retrieve_documents` / `lookup_calendar`, etc.).
2. **Loop main-path boundary**: the production Loop is controlled by the Python `LoopEngine` + Redis Stream Worker, and pi executes Reflect through the unified
   `/v1/agent/run`; `loop.ts` and `/loop/run` are kept only as compatibility/standalone experiment paths and are not responsible for production policy releases.
3. **Narrowed responsibilities**: pi does not read the business database and does not decide department permissions, memory writes, or policy releases.
4. **Failure degradation**: when the Runtime is unavailable or its output does not satisfy the schema, the Python agents use their original local LLM/rule paths.
