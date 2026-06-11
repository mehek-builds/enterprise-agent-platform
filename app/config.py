"""Central configuration. Everything is env-var driven (12-factor): the same
image runs against Anthropic, OpenAI, or G42 Compass/JAIS by swapping env vars."""
import hashlib
import json
import os
from dataclasses import dataclass, field, asdict


@dataclass(frozen=True)
class ModelConfig:
    base_url: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    model: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    api_key: str = os.getenv("LLM_API_KEY", "")
    temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.0"))
    max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "2048"))


@dataclass(frozen=True)
class GovernanceConfig:
    # Budget rails: hard per-task and per-session token/cost ceilings.
    max_tokens_per_task: int = int(os.getenv("MAX_TOKENS_PER_TASK", "60000"))
    max_usd_per_task: float = float(os.getenv("MAX_USD_PER_TASK", "0.50"))
    max_llm_calls_per_task: int = int(os.getenv("MAX_LLM_CALLS_PER_TASK", "16"))
    max_validator_retries: int = int(os.getenv("MAX_VALIDATOR_RETRIES", "2"))
    redaction_enabled: bool = os.getenv("REDACTION_ENABLED", "true").lower() == "true"


@dataclass(frozen=True)
class AuthConfig:
    jwt_secret: str = os.getenv("JWT_SECRET", "dev-secret-change-me")
    jwt_algorithm: str = "HS256"
    token_ttl_seconds: int = int(os.getenv("TOKEN_TTL_SECONDS", "3600"))


# RBAC: role -> allowed tool name patterns, enforced at the graph layer
# (not just the API gateway). "*" = all registered pack tools.
ROLE_TOOL_ALLOWLIST: dict[str, list[str]] = {
    "admin": ["*"],
    "analyst": ["*"],          # analysts get all read/analyze tools; write-class
    # viewer is reporting-only: no raw ledger/HRIS queries, no analysis tools.
    # escalate stays available to every role as the safety valve.
    "viewer": ["generate_report", "aging_report", "cash_position",
               "lifecycle_status", "evaluate_supplier", "escalate"],
}
# Tools that are *recommend-only* regardless of role: any action consequence
# must flow through the escalation gate.
ESCALATION_ONLY_ACTIONS = {"execute_payment", "approve_hire", "award_contract"}

DB_PATH = os.getenv("AUDIT_DB_PATH", os.path.join(os.path.dirname(__file__), "..", "data", "audit.db"))
CHECKPOINT_DB_PATH = os.getenv("CHECKPOINT_DB_PATH", os.path.join(os.path.dirname(__file__), "..", "data", "checkpoints.db"))

VERSION = "1.2.0"  # chassis version; see CHANGELOG.md


def config_snapshot(domain: str, system_prompt: str, tool_names: list[str], role: str) -> dict:
    """The Traeco pattern: a full, hashable record of the exact configuration
    an agent session ran under. Written to the audit store at session start."""
    mc = ModelConfig()
    snap = {
        "chassis_version": VERSION,
        "domain": domain,
        "model": mc.model,
        "base_url": mc.base_url,
        "temperature": mc.temperature,
        "system_prompt_sha256": hashlib.sha256(system_prompt.encode()).hexdigest(),
        "tools": sorted(tool_names),
        "rbac_role": role,
        "governance": asdict(GovernanceConfig()),
    }
    snap["snapshot_sha256"] = hashlib.sha256(
        json.dumps(snap, sort_keys=True).encode()
    ).hexdigest()
    return snap
