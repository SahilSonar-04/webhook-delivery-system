import http from "k6/http";
import { check, sleep } from "k6";
import { randomString } from "https://jslib.k6.io/k6-utils/1.2.0/index.js";

const PROD_KEY = "pk_ZYMCvfaFth1hfWmHswRHUP7t3AeB_iAXBKiagLTwv78";
const BASE_URL = "http://localhost:8000";

export const options = {
  scenarios: {
    steady_delivery_load: {
      executor: "constant-arrival-rate",
      rate: 300,
      timeUnit: "1s",
      duration: "60s",
      preAllocatedVUs: 100,
      maxVUs: 300,
    },
  },
};

export default function () {
  const payload = JSON.stringify({
    event_type: "load.test",
    payload: { vu: __VU, iter: __ITER },
    idempotency_key: `delivery-scaling-${__VU}-${__ITER}-${randomString(8)}`,
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
    "queued 1": (r) => {
      try {
        return JSON.parse(r.body).queued === 1;
      } catch {
        return false;
      }
    },
  });
}
