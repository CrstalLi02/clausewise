import http from 'k6/http';
import { check } from 'k6';

export const options = {
  scenarios: {
    dept_agent: {
      executor: 'ramping-arrival-rate',
      startRate: Number(__ENV.START_RATE || 5),
      timeUnit: '1s',
      preAllocatedVUs: 20,
      maxVUs: 300,
      stages: [
        { target: Number(__ENV.TARGET_RATE || 50), duration: __ENV.RAMP || '30s' },
        { target: Number(__ENV.TARGET_RATE || 50), duration: __ENV.HOLD || '2m' },
      ],
    },
  },
  thresholds: { http_req_failed: ['rate<0.01'], http_req_duration: ['p(95)<8000'] },
};

export default function () {
  const base = __ENV.BASE_URL || 'http://localhost:8000';
  const dept = __ENV.DEPT_ID || 'dept_jwc';
  const token = __ENV.INTERNAL_API_TOKEN || '';
  const response = http.post(`${base}/api/v1/internal/dept/answer`, JSON.stringify({
    query: 'What is the word count requirement for the graduate thesis proposal?', dept_id: dept,
    session_id: `load-${__VU}-${__ITER}`, user_id: 'loadtest',
  }), { headers: { 'Content-Type': 'application/json', 'X-Internal-Token': token } });
  check(response, { 'status 200': (r) => r.status === 200 });
}
