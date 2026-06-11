# Integration Capabilities

The Human Capital Intelligence Agent's tools read data through one connector interface (fetch/normalize/cache, the pattern production-proven in Nucleus at Elemental Growth). Today the interface is backed by validated synthetic datasets; wiring a live enterprise system replaces the dataset read with the system call. Tool signatures, the agent graph, governance, RBAC, and the benchmark suite are unchanged by a connector swap, so live integrations inherit the submitted evidence.

## Named Systems Matrix

| Category | System | Integration mechanism |
|---|---|---|
| HRIS | Workday | REST/RaaS reports behind the `employees` and `comp_bands` data providers; replaces the synthetic 300-employee HRIS read |
| HRIS | SAP SuccessFactors | OData API behind the same `employees` provider interface |
| HRIS | Oracle HCM Cloud | HCM REST resources behind the same provider interface |
| ATS | Greenhouse | Harvest API behind the `candidates` provider feeding `screen_candidates`; scoring stays qualifications-only regardless of source |
| ATS | Taleo | Taleo Connect / REST behind the same `candidates` provider |
| ATS | SmartRecruiters | Posting/candidate API behind the same `candidates` provider |
| Payroll / comp | ADP (or equivalent payroll) | Comp and band data behind the `comp_bands` provider feeding `comp_benchmark` |
| Cloud runtime | Azure Container Apps | `az containerapp up --image <registry>/g42-agent-platform --target-port 8000`; same image, same env vars |
| Cloud runtime | AKS | Same image as a Deployment; N replicas, shared Azure Files volume or external DB paths for scale |
| Sovereign model | G42 Compass (JAIS, Llama 3, gpt-oss, Azure OpenAI) | `LLM_BASE_URL` + `LLM_MODEL` + `LLM_API_KEY` env swap; zero code change; re-benchmark with the shipped harness before promotion |
| Document and collaboration stack | M365, SharePoint, Monday.com (InceptionClaw alignment) | Document ingestion path with the same Presidio redaction and injection defense applied to ingested content |
| Observability | Any OTLP collector | `OTEL_EXPORTER_OTLP_ENDPOINT`; every LLM call, tool call, redaction event, and escalation exported as spans into G42's existing observability stack |

## Authentication, RBAC, and PII Handling at the Boundary

| Control | Mechanism |
|---|---|
| Authentication | Scoped API key exchanged for a short-TTL JWT with a role claim (`POST /v1/auth/token`); no unauthenticated path reaches the agent; forged and missing tokens rejected at the gateway (verified in the adversarial suite) |
| RBAC | Per-role tool allowlists enforced at the graph layer: tools outside the role's allowlist are absent from the model's tool schema. Viewer is reporting-only; `approve_hire` is escalation-only for every role |
| PII redaction | Presidio on both input and output, so candidate and employee PII is stripped before it reaches the LLM endpoint and again before the response leaves the platform. This holds for any model endpoint, including external ones, and applies equally to ingested documents |
| Rate limiting | Per-principal limits with Retry-After on all authenticated endpoints; graceful 429 shedding under burst (verified under load: zero 5xx) |
| Audit at the boundary | Every connector call is a tool call: checkpointed in SQLite, traced in OTel, attributable to a config snapshot and a role |

## Integration Sequencing

1. Deploy the image against G42's runtime (Container Apps or AKS) with Compass as the model endpoint: configuration only, day one.
2. Wire HRIS read connectors (Workday or SuccessFactors) behind the `employees` provider; re-run the golden suite and bias parity suite against live-shaped data.
3. Wire ATS connectors behind the `candidates` provider; parity monitoring runs on live candidate flow before any autonomy increase (see thirty-sixty-ninety.md).
4. Export OTel to G42's collector and point `/v1/impact` at the value-linked compensation review.
