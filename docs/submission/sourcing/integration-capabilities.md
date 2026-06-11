# Integration Capabilities

Agent: Strategic Sourcing Intelligence Agent (jobs.g42.ai req 732965422), v1.2.1, developer Mehek Mandal.

## Integration Principle

Every sourcing tool reads data through one connector interface (fetch, normalize, cache: the Nucleus pattern, proven in the Elemental Growth production pipeline). The submitted benchmarks run against validated synthetic datasets behind that interface; wiring a live system replaces the dataset read with the system call. Tool signatures, the agent graph, governance, and benchmarks are unchanged: no graph changes, no re-architecture.

## Integration Matrix

| System | Category | Mechanism |
|---|---|---|
| SAP Ariba | P2P (primary) | Implements the `suppliers`, `purchase_orders`, and requisition data providers behind the existing connector interface; 3-way match and intake tools consume it unchanged |
| Coupa | P2P (primary) | Same provider interface as Ariba; swap is a connector implementation, not an agent change |
| Oracle Procurement Cloud | P2P | Same provider interface; PO, receipt, and invoice reads map to `match_goods_receipt` inputs |
| Icertis | CLM (primary) | Implements the `contracts` provider; `contract_review` term extraction and risk rules run unchanged |
| DocuSign CLM | CLM | Same `contracts` provider interface as Icertis |
| Supplier master / ERP (SAP, Oracle, Dynamics) | Master data | Implements the `suppliers` provider feeding `evaluate_supplier` and `sourcing_recommendation` |
| M365 / SharePoint / Monday.com | Document and workflow (InceptionClaw alignment) | Document ingestion path through the same redaction and injection-defense pipeline verified in adversarial testing |
| Azure Container Apps / AKS | Deployment | Single cloud-agnostic Docker image, env-var configured; `az containerapp up` documented in the runbook; horizontal scale via replicas sharing a mounted volume |
| OTLP collector (any) | Observability | OTel spans for every LLM call and tool call (latency, tokens, redaction events) export to collectors G42 already runs |
| G42 Compass (JAIS, Llama 3, gpt-oss, Azure OpenAI) | Sovereign model layer | One OpenAI-compatible client; `LLM_BASE_URL` and `LLM_MODEL` env swap, zero code change |

CRM and analytics platform integration is supported through the same connector interface.

## Authentication, RBAC, and Data Protection

| Control | Implementation |
|---|---|
| Authentication | Scoped API keys exchanged for short-lived JWTs (`POST /v1/auth/token`, role claim, configurable TTL); forged and missing tokens rejected at the gateway (adversarial cases 1 and 2) |
| RBAC | Per-role tool allowlists enforced at the graph layer: tools outside the role are absent from the model's tool schema, so they cannot be invoked even under injection; viewer is reporting-only, `escalate` available to all roles |
| PII redaction | Microsoft Presidio on input and output, 92% seeded-token efficacy, with domain false-positive filters so currency figures and domain terms are not over-redacted |
| Rate limiting | Per-principal limits on all authenticated endpoints with Retry-After on 429 |
| Request validation | Schema and size limits at the gateway (oversized and malformed payloads rejected with 422) |
| Budget rails | Hard per-task ceilings on tokens, cost, and LLM calls, env-configurable |

## Integration Endpoints

| Endpoint | Purpose |
|---|---|
| `POST /v1/auth/token` | Exchange scoped API key for JWT with role claim |
| `POST /v1/agents/sourcing/tasks` | Run a sourcing task |
| `GET /v1/audit/{session_id}` | Full replayable session trail |
| `GET /v1/impact`, `GET /dashboard` | Enterprise impact telemetry rollup |
| `GET /health` | Liveness, version, registered agents (Docker HEALTHCHECK) |
