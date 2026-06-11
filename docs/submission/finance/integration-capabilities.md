# Integration Capabilities

## Business Outcome First

The agent runs against G42's existing systems without rework: live ERP/GL, subledger, and treasury connectors drop in behind the same interface the validated synthetic datasets use today, the model layer points at G42 Compass with two environment variables, and observability exports to whatever OTLP collector G42 already operates. Tool signatures, the agent graph, governance, and the benchmark suite are unchanged by any of these swaps.

## Architecture of Integration

Four integration surfaces, each independent:

1. Connector layer: one interface (fetch/normalize/cache, the Nucleus production pattern) behind every data tool.
2. Model layer: one OpenAI-compatible client, endpoint and model set by env vars.
3. Observability: OTel spans with vendor-neutral OTLP export.
4. API surface: REST + JWT for any upstream orchestrator or UI.

## Integration Matrix

| System | Category | Integration mechanism | Notes |
|---|---|---|---|
| SAP S/4HANA | ERP / GL | Connector interface: `query_ledger`, `analyze_variance` data providers | Primary; replaces synthetic GL read, no graph changes |
| Oracle Fusion | ERP / GL | Connector interface: GL data providers | Primary |
| Microsoft Dynamics 365 Finance | ERP / GL, AP/AR | Connector interface: GL and `aging_report` providers | Primary |
| AP/AR subledger systems | Subledger | Connector interface: `aging_report` provider | |
| Kyriba and treasury management systems | Treasury | Connector interface: `cash_position` provider | |
| G42 Compass (JAIS, Llama 3, gpt-oss-20B/120B, Azure OpenAI GPT-4 family) | Sovereign LLM | OpenAI-compatible model layer: `LLM_BASE_URL` + `LLM_MODEL` env swap | Zero code change; re-benchmark via shipped harness |
| Azure Container Apps | Deployment | Single Docker image, `az containerapp up`, env-var config | Documented path in deployment runbook |
| Azure Kubernetes Service (AKS) | Deployment | Same image and env vars; N replicas | Horizontal scale |
| Azure Files | State | Shared volume for audit + checkpoint SQLite stores | Or repoint DB paths at a managed database |
| M365 / SharePoint / Monday.com | Document and workflow (InceptionClaw stack) | Document ingestion path through the connector interface; same redaction and injection defense | |
| OTLP-compatible observability (any collector) | Monitoring | OTel span export: every LLM call, tool call, redaction event | Vendor-neutral |
| Upstream orchestrators, approval UIs | API consumers | REST API + JWT (`/v1/auth/token`, `/v1/agents/finance/tasks`, `/v1/audit/{id}`, `/v1/impact`) | Role claim drives RBAC |

CRM and analytics platform integration is supported through the same connector interface, with ERP/GL remaining the primary integration target for the finance agent.

## Authentication and Data Protection

| Control | Implementation |
|---|---|
| Authentication | Scoped API key exchanged for a JWT (HS256, configurable TTL) at `/v1/auth/token`; role claim embedded |
| RBAC | Per-role tool allowlists enforced at the graph layer: tools outside the role's allowlist are absent from the model's tool schema (admin, analyst, viewer roles; viewer is reporting-only) |
| Rate limiting | Per-principal, on all authenticated endpoints; graceful 429 + Retry-After |
| PII protection | Microsoft Presidio redaction on both input and output, with an audit event per redaction; 92% seeded-PII efficacy |
| Request validation | Schema and max-length validation at the gateway (oversized and malformed payloads rejected with 422) |
| Audit traceability | Hash-addressed config snapshots, replayable LangGraph checkpoints, OTel spans; full trail at `GET /v1/audit/{session_id}` |

## Connector Contract

Each live connector implements fetch (call the source system), normalize (map to the tool's stable output schema), and cache (bounded freshness window). This is the pattern proven in Nucleus (2025, Elemental Growth production analytics pipeline). Because tools consume the normalized schema, swapping synthetic data for a live system changes no tool signature, no prompt, and no benchmark; the golden suite re-runs as-is against live connectors to validate the integration.
