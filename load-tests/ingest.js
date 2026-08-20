import http from "k6/http";
import { check, sleep } from "k6";
import { randomString } from "https://jslib.k6.io/k6-utils/1.2.0/index.js";

const PROD_KEY = "pk_ZYMCvfaFth1hfWmHswRHUP7t3AeB_iAXBKiagLTwv78";
const BASE_URL = "http://localhost:8000";

export const options = {
  scenarios: {
    ramping_load: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "30s", target: 10 },
        { duration: "30s", target: 10 },
        { duration: "30s", target: 100 },
        { duration: "30s", target: 100 },
        { duration: "30s", target: 1000 },
        { duration: "60s", target: 1000 },
        { duration: "20s", target: 0 },
      ],
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.05"],
    http_req_duration: ["p(95)<2000"],
  },
};

export default function () {
  const payload = JSON.stringify({
    event_type: "load.test",
    payload: { vu: __VU, iter: __ITER },
    idempotency_key: `loadtest-${__VU}-${__ITER}-${randomString(8)}`,
  });

  const params = {
    headers: {
      "Content-Type": "application/json",
      "x-api-key": PROD_KEY,
    },
  };

  const res = http.post(`${BASE_URL}/api/v1/events`, payload, params);

  check(res, {
    "status is 202": (r) => r.status === 202,
    "response has event_id": (r) => {
      try {
        return JSON.parse(r.body).event_id !== undefined;
      } catch {
        return false;
      }
    },
  });

  sleep(0.1);
}
