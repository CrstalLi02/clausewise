# Deployment and High-Concurrency Design

## 1. Local Development (Docker, Recommended)

```bash
cd program
cp .env.example .env     # Fill in secrets
docker compose up --build
```

## 2. Production Deployment (K8s)

The `deploy/` directory provides:

- `deploy/k8s/` — native YAML manifests (namespace / mongodb / redis / orchestrator / loop-engine / dept-agent / gateway / monitoring)
- `deploy/helm/clausewise/` — Helm Chart for templated deployment of new department agents

```bash
helm install clausewise deploy/helm/clausewise -n clausewise --create-namespace \
  --set secrets.deepseekApiKey=... --set secrets.relayApiKey=...
```

### Department Agent Autoscaling

Each department agent is an independent Deployment + HPA, scaled on the custom Pods metric `clausewise_dept_agent_inflight`:

- Low-traffic departments (International Exchange Office): `minReplicas=1`
- High-traffic departments (Academic Affairs / Student Affairs): `minReplicas=2`, `maxReplicas=20`

```yaml
# Add a new department agent (templated)
helm upgrade --install dept-agent-x deploy/helm/clausewise -n clausewise \
  --set department.id=dept_x --set department.name="XX Office"
```

## 3. Key High-Concurrency Design Points

| Design Point | Implementation |
|---|---|
| Department-level isolation | Independent Deployment + HPA, Pod anti-affinity |
| Shared retrieval | Shared Mongo vectors + stateless BM25 over active chunks, avoiding index drift between Pods |
| Async processing | Ingestion / feedback wake-ups / Loop go through Redis Stream; uploaded files are shared between backend/worker via an RWX PVC |
| Session memory | Redis TTL state stores only summaries, entities, and chunk IDs; long-term events go into Mongo TTL collections |
| Rate limiting and degradation | Ingress rate limiting; when a department service fails, fall back to shared retrieval and mark degraded departments |
| Connection pooling | motor async MongoDB + redis.asyncio connection pools |
| Warm-up | Scale out before peak hours + preload hot FAQs |

## 4. Observability

The current manifests include Prometheus, Grafana, and the Prometheus Adapter; Loki/OpenTelemetry are not yet implemented in the repository manifests.

- Metrics endpoint: `/metrics` (prometheus_client)
- Department HPA metric: `clausewise_dept_agent_inflight`
- Q&A metrics: `clausewise_query_latency_seconds`, `clausewise_answer_adoption_total`, `clausewise_skill_trigger_total`
- pi execution metric: `clausewise_pi_agent_execution_total{agent,status}`, distinguishing success/fallback/error/disabled
