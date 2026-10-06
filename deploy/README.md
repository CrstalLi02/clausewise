# Deployment (Docker / Kubernetes / Helm)

## Directory Structure

```
deploy/
├── README.md
├── k8s/                     # Native K8s manifests
│   ├── namespace.yaml
│   ├── secrets.yaml.example
│   ├── mongodb.yaml
│   ├── redis.yaml
│   ├── backend.yaml         # Orchestrator + API (global service, HPA)
│   ├── loop-engine.yaml     # Loop Engine (standalone background worker)
│   ├── dept-agent.yaml      # Department agent (templated example)
│   ├── ingress.yaml
│   ├── monitoring.yaml      # Prometheus / Grafana
│   ├── prometheus-adapter.yaml # Custom HPA metric for department agents
│   └── uploads-pvc.yaml     # Shared uploaded files for backend/worker
└── helm/
    └── clausewise/              # Helm Chart (templated deployment of new department agents)
        ├── Chart.yaml
        ├── values.yaml
        └── templates/
```

## 1. Docker (Local, Recommended)

See `docker-compose.yml` and `README.md` in the project root.

## 2. Native Kubernetes Deployment

```bash
kubectl apply -f deploy/k8s/namespace.yaml
# Create the secret first (copy the example and fill in real secrets)
cp deploy/k8s/secrets.yaml.example deploy/k8s/secrets.yaml
kubectl apply -f deploy/k8s/secrets.yaml
kubectl apply -f deploy/k8s/mongodb.yaml
kubectl apply -f deploy/k8s/redis.yaml
kubectl apply -f deploy/k8s/uploads-pvc.yaml
kubectl apply -f deploy/k8s/backend.yaml
kubectl apply -f deploy/k8s/loop-engine.yaml
kubectl apply -f deploy/k8s/dept-agent.yaml
kubectl apply -f deploy/k8s/monitoring.yaml
kubectl apply -f deploy/k8s/prometheus-adapter.yaml
kubectl apply -f deploy/k8s/ingress.yaml
```

## 3. Helm Deployment (Recommended, Templated Department Agents)

```bash
helm install clausewise deploy/helm/clausewise -n clausewise --create-namespace \
  --set secrets.deepseekApiKey=sk-... \
  --set secrets.relayApiKey=sk-... \
  --set secrets.authSecret=<strong-random-value> \
  --set secrets.internalApiToken=<strong-random-value> \
  --set secrets.mongodbUri="mongodb://user:pass@mongodb:27017/clausewise?authSource=admin" \
  --set secrets.redisAddr="redis://:pass@redis:6379"
```

> Note: `--set` key names must match the `secrets.*` structure in `values.yaml` (e.g., `secrets.mongodbUri`, `secrets.redisAddr`);
> misspelled keys are silently ignored by Helm, and the default placeholder values are used instead.

### Adding a Department Agent

```bash
# Deploy a new department from the same Chart template (each department gets its own Deployment + HPA)
helm upgrade --install dept-agent-x deploy/helm/clausewise -n clausewise \
  --set department.id=dept_x --set department.name="XX Office" \
  --set department.minReplicas=1 --set department.maxReplicas=10
```

## 4. High-Concurrency Design (Technical Design Section 7.3)

| Design Point | K8s Implementation |
|---|---|
| Department-level isolation | Independent Deployment + HPA per department, Pod anti-affinity |
| Autoscaling | HPA scales on in-flight requests per department agent via the Prometheus Adapter; high-traffic departments use maxReplicas=20 |
| Rate limiting and degradation | Rate limiting at the Ingress/Gateway layer; on LLM failure, degrade to FAQ/source-text retrieval |
| Observability | Prometheus (`/metrics`) + Grafana |

`uploads-pvc.yaml` requires the cluster to support `ReadWriteMany`. After deployment, verify the custom metric and HPA:

```bash
kubectl get --raw /apis/custom.metrics.k8s.io/v1beta1 | grep clausewise_dept_agent_inflight
kubectl get hpa -n clausewise
```

For the 1→20 Pod load-validation commands and pass thresholds, see `../loadtest/README.md`.

## 5. Building Images

```bash
# Backend
docker build -t clausewise-agent:v1.0 -f ../backend/Dockerfile ../backend
# Frontend
docker build -t clausewise-web:v1.0 ../web
```

## 6. pi Agent Runtime + Next.js Frontend

Python owns the control plane, and pi handles unified probabilistic agent execution. The service topology is:

| Service | Manifest / Build |
|---|---|
| Python backend | `backend.yaml` + `../backend/Dockerfile` |
| pi Agent Runtime (Node/TS) | `pi-agent.yaml` + `../services/pi-agent/Dockerfile` |
| Next.js frontend | `../web/Dockerfile` |

For one-command local full-stack startup, see the root `docker-compose.yml` (includes mongodb/redis/backend/pi-agent/web).
The pi Runtime is deployed by default in production; when the service is unavailable, Python automatically degrades to local agents. All execution endpoints require the internal token.
