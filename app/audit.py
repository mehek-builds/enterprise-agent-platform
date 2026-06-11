"""Audit store (layer 1 and 3 of the audit design; layer 2 is the LangGraph
SQLite checkpointer). Independently queryable SQLite tables:

  config_snapshots  - full agent config at session start (Traeco pattern)
  audit_events      - every LLM call, tool call, redaction, escalation, validation
  impact_telemetry  - per-task impact rollup for value-linked compensation
"""
import json
import os
import sqlite3
import threading
import time
import uuid

from .config import DB_PATH

_lock = threading.Lock()


def _conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.execute("PRAGMA journal_mode=WAL")
    return c


def init_db() -> None:
    with _lock, _conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS config_snapshots (
                session_id TEXT PRIMARY KEY,
                ts REAL NOT NULL,
                domain TEXT NOT NULL,
                snapshot_json TEXT NOT NULL,
                snapshot_sha256 TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit_events (
                event_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                ts REAL NOT NULL,
                kind TEXT NOT NULL,        -- llm_call | tool_call | redaction | escalation | validation | error
                payload_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_events_session ON audit_events(session_id, ts);
            CREATE TABLE IF NOT EXISTS impact_telemetry (
                task_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                ts REAL NOT NULL,
                domain TEXT NOT NULL,
                task_type TEXT NOT NULL,
                completion_seconds REAL NOT NULL,
                human_equivalent_minutes REAL NOT NULL,
                tokens INTEGER NOT NULL,
                cost_usd REAL NOT NULL,
                escalated INTEGER NOT NULL,
                outcome TEXT NOT NULL      -- completed | escalated | failed
            );
            """
        )


def record_snapshot(session_id: str, domain: str, snapshot: dict) -> None:
    with _lock, _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO config_snapshots VALUES (?,?,?,?,?)",
            (session_id, time.time(), domain, json.dumps(snapshot), snapshot["snapshot_sha256"]),
        )


def record_event(session_id: str, kind: str, payload: dict) -> None:
    with _lock, _conn() as c:
        c.execute(
            "INSERT INTO audit_events VALUES (?,?,?,?,?)",
            (str(uuid.uuid4()), session_id, time.time(), kind, json.dumps(payload, default=str)),
        )


def record_impact(task_id: str, session_id: str, domain: str, task_type: str,
                  completion_seconds: float, human_equivalent_minutes: float,
                  tokens: int, cost_usd: float, escalated: bool, outcome: str) -> None:
    with _lock, _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO impact_telemetry VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (task_id, session_id, time.time(), domain, task_type, completion_seconds,
             human_equivalent_minutes, tokens, cost_usd, int(escalated), outcome),
        )


def session_trail(session_id: str) -> dict:
    """Full replayable trail for one session: snapshot + ordered events."""
    with _lock, _conn() as c:
        snap = c.execute(
            "SELECT snapshot_json FROM config_snapshots WHERE session_id=?", (session_id,)
        ).fetchone()
        events = c.execute(
            "SELECT ts, kind, payload_json FROM audit_events WHERE session_id=? ORDER BY ts",
            (session_id,),
        ).fetchall()
    return {
        "session_id": session_id,
        "config_snapshot": json.loads(snap[0]) if snap else None,
        "events": [{"ts": ts, "kind": k, "payload": json.loads(p)} for ts, k, p in events],
    }


def impact_rollup() -> dict:
    """Enterprise impact rollup: the numbers value-linked compensation is
    computed from. Human-equivalent minutes are documented assumptions per
    task type (see docs/impact-assumptions.md)."""
    with _lock, _conn() as c:
        rows = c.execute(
            """SELECT domain, COUNT(*), SUM(completion_seconds), SUM(human_equivalent_minutes),
                      SUM(tokens), SUM(cost_usd), SUM(escalated),
                      SUM(CASE WHEN outcome='completed' THEN 1 ELSE 0 END)
               FROM impact_telemetry GROUP BY domain"""
        ).fetchall()
    out = {"domains": {}, "totals": {"tasks": 0, "hours_saved": 0.0, "cost_usd": 0.0}}
    for d, n, secs, heq_min, toks, cost, esc, done in rows:
        agent_hours = (secs or 0) / 3600
        human_hours = (heq_min or 0) / 60
        out["domains"][d] = {
            "tasks": n,
            "completed": done,
            "escalated": esc,
            "agent_hours": round(agent_hours, 3),
            "human_equivalent_hours": round(human_hours, 2),
            "hours_saved": round(human_hours - agent_hours, 2),
            "tokens": toks,
            "cost_usd": round(cost or 0, 4),
            "cost_per_task_usd": round((cost or 0) / n, 4) if n else 0,
            "escalation_rate": round(esc / n, 3) if n else 0,
        }
        out["totals"]["tasks"] += n
        out["totals"]["hours_saved"] += human_hours - agent_hours
        out["totals"]["cost_usd"] += cost or 0
    out["totals"]["hours_saved"] = round(out["totals"]["hours_saved"], 2)
    out["totals"]["cost_usd"] = round(out["totals"]["cost_usd"], 4)
    return out
