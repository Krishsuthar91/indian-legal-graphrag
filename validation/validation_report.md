# HHGR Legal QA — Manual Validation Report

End-to-end run against the local `/query` pipeline (deterministic mock LLM).

## Summary

| Metric | Value |
|--------|-------|
| Total queries | 130 |
| Pass | 40 |
| Fail | 90 |
| Pass rate | 30.8% |
| Average confidence | 0.265 |
| Average latency | 154.7 ms |
| Wrong-document retrievals | 0 |
| Hallucinations prevented | 40 |
| Grounding-guard activations | 122 |

## By category

| Category | Cases | Pass | Fail | Pass rate | Avg conf | Avg ms |
|----------|-------|------|------|-----------|----------|--------|
| Category 1 | 41 | 0 | 41 | 0.0% | 0.243 | 83.7 |
| Category 2 | 24 | 0 | 24 | 0.0% | 0.246 | 116.6 |
| Category 3 | 10 | 0 | 10 | 0.0% | 0.341 | 139.2 |
| Category 4 | 15 | 0 | 15 | 0.0% | 0.337 | 134.5 |
| Category 5 | 20 | 20 | 0 | 100.0% | 0.261 | 158.8 |
| Category 6 | 20 | 20 | 0 | 100.0% | 0.246 | 364.7 |

## Top failure patterns

- 90x verification status mismatch
- 82x grounding-guard block mismatch
- 39x wrong/absent top section

## Per-case results

| Case | Status | Conf | Blocked | Top section | Top doc | Result |
|------|--------|------|---------|-------------|---------|--------|
| 1.001 | insufficient | 0.203 | True  | 1                | ICA (Contract Act)   | FAIL |
| 1.002 | insufficient | 0.221 | True  | 2                | ICA (Contract Act)   | FAIL |
| 1.003 | insufficient | 0.246 | True  | 3                | ICA (Contract Act)   | FAIL |
| 1.004 | insufficient | 0.244 | True  | 4                | ICA (Contract Act)   | FAIL |
| 1.005 | insufficient | 0.230 | True  | 5                | ICA (Contract Act)   | FAIL |
| 1.006 | insufficient | 0.227 | True  | 6                | ICA (Contract Act)   | FAIL |
| 1.007 | insufficient | 0.283 | True  | 7                | ICA (Contract Act)   | FAIL |
| 1.008 | insufficient | 0.231 | True  | 8                | ICA (Contract Act)   | FAIL |
| 1.009 | insufficient | 0.247 | True  | 9                | ICA (Contract Act)   | FAIL |
| 1.010 | insufficient | 0.229 | True  | 10               | ICA (Contract Act)   | FAIL |
| 1.011 | insufficient | 0.237 | True  | 10               | ICA (Contract Act)   | FAIL |
| 1.012 | insufficient | 0.252 | True  | 11               | ICA (Contract Act)   | FAIL |
| 1.013 | insufficient | 0.231 | True  | 12               | ICA (Contract Act)   | FAIL |
| 1.014 | insufficient | 0.234 | True  | 13               | ICA (Contract Act)   | FAIL |
| 1.015 | insufficient | 0.288 | True  | 14               | ICA (Contract Act)   | FAIL |
| 1.016 | insufficient | 0.241 | True  | 15               | ICA (Contract Act)   | FAIL |
| 1.017 | insufficient | 0.241 | True  | 16               | ICA (Contract Act)   | FAIL |
| 1.018 | insufficient | 0.244 | True  | 17               | ICA (Contract Act)   | FAIL |
| 1.019 | insufficient | 0.239 | True  | 18               | ICA (Contract Act)   | FAIL |
| 1.020 | insufficient | 0.255 | True  | 19               | ICA (Contract Act)   | FAIL |
| 1.021 | insufficient | 0.248 | True  | 20               | ICA (Contract Act)   | FAIL |
| 1.022 | insufficient | 0.228 | True  | 23               | ICA (Contract Act)   | FAIL |
| 1.023 | insufficient | 0.261 | True  | 25               | ICA (Contract Act)   | FAIL |
| 1.024 | insufficient | 0.229 | True  | 27               | ICA (Contract Act)   | FAIL |
| 1.025 | insufficient | 0.232 | True  | 37               | ICA (Contract Act)   | FAIL |
| 1.026 | insufficient | 0.245 | True  | 56               | ICA (Contract Act)   | FAIL |
| 1.027 | insufficient | 0.230 | True  | 65               | ICA (Contract Act)   | FAIL |
| 1.028 | insufficient | 0.233 | True  | 72               | ICA (Contract Act)   | FAIL |
| 1.029 | insufficient | 0.241 | True  | 73               | ICA (Contract Act)   | FAIL |
| 1.030 | insufficient | 0.231 | True  | 74               | ICA (Contract Act)   | FAIL |
| 1.031 | insufficient | 0.231 | True  | 124              | ICA (Contract Act)   | FAIL |
| 1.032 | insufficient | 0.248 | True  | 126              | ICA (Contract Act)   | FAIL |
| 1.033 | insufficient | 0.242 | True  | 128              | ICA (Contract Act)   | FAIL |
| 1.034 | insufficient | 0.229 | True  | 148              | ICA (Contract Act)   | FAIL |
| 1.035 | insufficient | 0.254 | True  | 171              | ICA (Contract Act)   | FAIL |
| 1.036 | insufficient | 0.239 | True  | 172              | ICA (Contract Act)   | FAIL |
| 1.037 | insufficient | 0.235 | True  | 182              | ICA (Contract Act)   | FAIL |
| 1.038 | insufficient | 0.257 | True  | 185              | ICA (Contract Act)   | FAIL |
| 1.039 | insufficient | 0.237 | True  | 188              | ICA (Contract Act)   | FAIL |
| 1.040 | insufficient | 0.296 | True  | 178A             | ICA (Contract Act)   | FAIL |
| 1.041 | insufficient | 0.278 | True  | 16               | ICA (Contract Act)   | FAIL |
| 2.001 | insufficient | 0.193 | True  | 14               | ICA (Contract Act)   | FAIL |
| 2.002 | insufficient | 0.178 | True  | 14               | ICA (Contract Act)   | FAIL |
| 2.003 | insufficient | 0.248 | True  | 23               | ICA (Contract Act)   | FAIL |
| 2.004 | insufficient | 0.206 | True  | 14               | ICA (Contract Act)   | FAIL |
| 2.005 | insufficient | 0.248 | True  | 38               | ICA (Contract Act)   | FAIL |
| 2.006 | insufficient | 0.241 | True  | 16               | ICA (Contract Act)   | FAIL |
| 2.007 | insufficient | 0.236 | True  | 14               | ICA (Contract Act)   | FAIL |
| 2.008 | insufficient | 0.224 | True  | 14               | ICA (Contract Act)   | FAIL |
| 2.009 | insufficient | 0.180 | True  | 14               | ICA (Contract Act)   | FAIL |
| 2.010 | insufficient | 0.232 | True  | 19               | ICA (Contract Act)   | FAIL |
| 2.011 | insufficient | 0.211 | True  | 19               | ICA (Contract Act)   | FAIL |
| 2.012 | insufficient | 0.245 | True  | 25               | ICA (Contract Act)   | FAIL |
| 2.013 | insufficient | 0.223 | True  | 19               | ICA (Contract Act)   | FAIL |
| 2.014 | insufficient | 0.315 | True  | 31               | ICA (Contract Act)   | FAIL |
| 2.015 | insufficient | 0.265 | True  | 25               | ICA (Contract Act)   | FAIL |
| 2.016 | insufficient | 0.298 | True  | 129              | ICA (Contract Act)   | FAIL |
| 2.017 | insufficient | 0.232 | True  | 124              | ICA (Contract Act)   | FAIL |
| 2.018 | insufficient | 0.195 | True  | 148              | ICA (Contract Act)   | FAIL |
| 2.019 | insufficient | 0.229 | True  | 178A             | ICA (Contract Act)   | FAIL |
| 2.020 | insufficient | 0.239 | True  | 185              | ICA (Contract Act)   | FAIL |
| 2.021 | insufficient | 0.278 | True  | 16               | ICA (Contract Act)   | FAIL |
| 2.022 | insufficient | 0.341 | True  | 22               | ICA (Contract Act)   | FAIL |
| 2.023 | insufficient | 0.272 | True  | 26               | ICA (Contract Act)   | FAIL |
| 2.024 | insufficient | 0.364 | True  | 154              | ICA (Contract Act)   | FAIL |
| 3.001 | insufficient | 0.338 | True  | 65               | ICA (Contract Act)   | FAIL |
| 3.002 | insufficient | 0.407 | True  | 5                | ICA (Contract Act)   | FAIL |
| 3.003 | insufficient | 0.319 | True  | 14               | ICA (Contract Act)   | FAIL |
| 3.004 | insufficient | 0.324 | True  | 14               | ICA (Contract Act)   | FAIL |
| 3.005 | insufficient | 0.372 | True  | 25               | ICA (Contract Act)   | FAIL |
| 3.006 | insufficient | 0.325 | True  | 124              | ICA (Contract Act)   | FAIL |
| 3.007 | insufficient | 0.372 | True  | 178A             | ICA (Contract Act)   | FAIL |
| 3.008 | insufficient | 0.313 | True  | 191              | ICA (Contract Act)   | FAIL |
| 3.009 | insufficient | 0.275 | True  | 64               | ICA (Contract Act)   | FAIL |
| 3.010 | insufficient | 0.361 | True  | 5                | ICA (Contract Act)   | FAIL |
| 4.001 | insufficient | 0.311 | False | 72               | ICA (Contract Act)   | FAIL |
| 4.002 | insufficient | 0.319 | True  | 16               | ICA (Contract Act)   | FAIL |
| 4.003 | insufficient | 0.394 | True  | 25               | ICA (Contract Act)   | FAIL |
| 4.004 | insufficient | 0.327 | False | 16               | ICA (Contract Act)   | FAIL |
| 4.005 | insufficient | 0.346 | True  | 26               | ICA (Contract Act)   | FAIL |
| 4.006 | insufficient | 0.286 | False | 69               | ICA (Contract Act)   | FAIL |
| 4.007 | insufficient | 0.307 | False | 31               | ICA (Contract Act)   | FAIL |
| 4.008 | insufficient | 0.297 | False | 69               | ICA (Contract Act)   | FAIL |
| 4.009 | insufficient | 0.369 | True  | 152              | ICA (Contract Act)   | FAIL |
| 4.010 | insufficient | 0.366 | True  | 126              | ICA (Contract Act)   | FAIL |
| 4.011 | insufficient | 0.329 | False | 55               | ICA (Contract Act)   | FAIL |
| 4.012 | insufficient | 0.434 | True  | 39               | ICA (Contract Act)   | FAIL |
| 4.013 | insufficient | 0.306 | False | 227              | ICA (Contract Act)   | FAIL |
| 4.014 | insufficient | 0.366 | True  | 178A             | ICA (Contract Act)   | FAIL |
| 4.015 | insufficient | 0.302 | False | 19               | ICA (Contract Act)   | FAIL |
| 5.001 | insufficient | 0.236 | True  | 14               | ICA (Contract Act)   | PASS |
| 5.002 | insufficient | 0.184 | True  | 14               | ICA (Contract Act)   | PASS |
| 5.003 | insufficient | 0.247 | True  | 19               | ICA (Contract Act)   | PASS |
| 5.004 | insufficient | 0.300 | True  | 376DA            | IPC (Penal Code)     | PASS |
| 5.005 | insufficient | 0.271 | True  | 14               | ICA (Contract Act)   | PASS |
| 5.006 | insufficient | 0.236 | True  | 14               | ICA (Contract Act)   | PASS |
| 5.007 | insufficient | 0.246 | True  | 14               | ICA (Contract Act)   | PASS |
| 5.008 | insufficient | 0.267 | True  | 376DA            | IPC (Penal Code)     | PASS |
| 5.009 | insufficient | 0.330 | True  | 16               | ICA (Contract Act)   | PASS |
| 5.010 | insufficient | 0.277 | True  | 173              | ICA (Contract Act)   | PASS |
| 5.011 | insufficient | 0.317 | True  | 141              | ICA (Contract Act)   | PASS |
| 5.012 | insufficient | 0.236 | True  | 16               | ICA (Contract Act)   | PASS |
| 5.013 | insufficient | 0.226 | True  | 207              | ICA (Contract Act)   | PASS |
| 5.014 | insufficient | 0.172 | True  | 129              | ICA (Contract Act)   | PASS |
| 5.015 | insufficient | 0.216 | True  | 7                | ICA (Contract Act)   | PASS |
| 5.016 | insufficient | 0.275 | True  | 16               | ICA (Contract Act)   | PASS |
| 5.017 | insufficient | 0.231 | True  | ii               | IPC (Penal Code)     | PASS |
| 5.018 | insufficient | 0.336 | True  | 294A             | ICA (Contract Act)   | PASS |
| 5.019 | insufficient | 0.306 | True  | b                | IPC (Penal Code)     | PASS |
| 5.020 | insufficient | 0.314 | True  | 294A             | ICA (Contract Act)   | PASS |
| 6.001 | insufficient | 0.247 | True  | 376              | IPC (Penal Code)     | PASS |
| 6.002 | insufficient | 0.303 | True  | 31               | IPC (Penal Code)     | PASS |
| 6.003 | insufficient | 0.215 | True  | 172              | ICA (Contract Act)   | PASS |
| 6.004 | insufficient | 0.194 | True  | 14               | ICA (Contract Act)   | PASS |
| 6.005 | insufficient | 0.132 | True  | 17               | IPC (Penal Code)     | PASS |
| 6.006 | insufficient | 0.279 | True  | 31               | IPC (Penal Code)     | PASS |
| 6.007 | insufficient | 0.231 | True  | 376              | IPC (Penal Code)     | PASS |
| 6.008 | insufficient | 0.255 | True  | 31               | IPC (Penal Code)     | PASS |
| 6.009 | insufficient | 0.270 | True  | 31               | IPC (Penal Code)     | PASS |
| 6.010 | insufficient | 0.300 | True  | 178A             | ICA (Contract Act)   | PASS |
| 6.011 | insufficient | 0.239 | True  | b                | IPC (Penal Code)     | PASS |
| 6.012 | insufficient | 0.254 | True  | 12               | ICA (Contract Act)   | PASS |
| 6.013 | insufficient | 0.233 | True  | 183              | ICA (Contract Act)   | PASS |
| 6.014 | insufficient | 0.264 | True  | 34               | ICA (Contract Act)   | PASS |
| 6.015 | insufficient | 0.249 | True  | ii               | IPC (Penal Code)     | PASS |
| 6.016 | insufficient | 0.198 | True  | 3                | IPC (Penal Code)     | PASS |
| 6.017 | insufficient | 0.237 | True  | 10               | ICA (Contract Act)   | PASS |
| 6.018 | insufficient | 0.245 | True  | 69               | ICA (Contract Act)   | PASS |
| 6.019 | insufficient | 0.232 | True  | 138              | ICA (Contract Act)   | PASS |
| 6.020 | insufficient | 0.342 | True  | 14               | ICA (Contract Act)   | PASS |
