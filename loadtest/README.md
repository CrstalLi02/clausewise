# Department Agent Elastic Load Test

Pin the target department Deployment to 1 replica and then 20 replicas, and run the following in the same environment with the same model and dataset:

```bash
k6 run --summary-export one.json department-agent.js
k6 run --summary-export twenty.json department-agent.js
python3 compare_results.py one.json twenty.json
```

Pass criteria: error rate below 1%, P95 under 8 seconds, and effective throughput with 20 replicas at least 2× that of 1 replica.
Actual gains are affected by external LLM rate limits, so production load tests must also monitor model-side TPM/RPM.
