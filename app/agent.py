"""LangGraph agent core (shared chassis).

Graph topology:

    agent -> (tool calls?) -> tools -> agent          (act loop)
    agent -> (final answer) -> validate
    validate -> pass -> END
    validate -> fail -> agent (critique fed back, bounded retries)
    any escalate() tool call -> END with status=escalated (human gate)
    budget breach at any point -> END with status=budget_exceeded

Every state transition is persisted by the SQLite checkpointer (replayable),
every LLM/tool/redaction/validation event lands in the audit store, and every
step emits an OTel span.
"""
import json
import re
import time
import uuid
from typing import Annotated, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph

from . import audit
from .config import (CHECKPOINT_DB_PATH, ESCALATION_ONLY_ACTIONS,
                     GovernanceConfig, ROLE_TOOL_ALLOWLIST, config_snapshot)
from .llm import LLMClient
from .packs.base import DomainPack
from .redaction import redact
from .telemetry import tracer


class AgentState(TypedDict, total=False):
    messages: list
    session_id: str
    domain: str
    role: str
    task_type: str
    llm_calls: int
    tokens: int
    cost_usd: float
    validation_failures: int
    status: str          # running | completed | escalated | budget_exceeded | failed
    escalation: dict
    final_answer: str
    tool_outputs: list


def allowed_tools(role: str, pack: DomainPack) -> set[str]:
    patterns = ROLE_TOOL_ALLOWLIST.get(role, [])
    names = set()
    for t in pack.tools:
        for p in patterns:
            if p == "*" or p == t.name or (p.endswith("*") and t.name.startswith(p[:-1])):
                names.add(t.name)
    return names


_NUM_RE = re.compile(r"-?\d[\d,]*\.?\d*")


def _numbers(text: str) -> set[str]:
    """Normalized significant numbers (abs >= 1000) for grounding checks."""
    out = set()
    for m in _NUM_RE.findall(text or ""):
        clean = m.replace(",", "")
        try:
            v = float(clean)
        except ValueError:
            continue
        if abs(v) >= 1000:
            out.add(f"{v:.2f}")
    return out


class AgentRunner:
    def __init__(self, pack: DomainPack, role: str, llm: LLMClient | None = None):
        self.pack = pack
        self.role = role
        self.llm = llm or LLMClient()
        self.gov = GovernanceConfig()
        self.allowed = allowed_tools(role, pack)
        self.graph = self._build()

    # --- nodes -------------------------------------------------------------

    def _agent_node(self, state: AgentState) -> AgentState:
        if state["llm_calls"] >= self.gov.max_llm_calls_per_task or \
           state["tokens"] >= self.gov.max_tokens_per_task or \
           state["cost_usd"] >= self.gov.max_usd_per_task:
            audit.record_event(state["session_id"], "escalation", {
                "reason": "budget_rail",
                "llm_calls": state["llm_calls"], "tokens": state["tokens"],
                "cost_usd": round(state["cost_usd"], 4),
            })
            return {**state, "status": "budget_exceeded"}
        with tracer().start_as_current_span("llm_call") as span:
            result = self.llm.chat(state["messages"], self.pack.tool_schemas(self.allowed))
            span.set_attribute("llm.input_tokens", result["input_tokens"])
            span.set_attribute("llm.output_tokens", result["output_tokens"])
            span.set_attribute("llm.latency_ms", round(result["latency_ms"], 1))
        audit.record_event(state["session_id"], "llm_call", {
            "model": self.llm.cfg.model,
            "input_tokens": result["input_tokens"], "output_tokens": result["output_tokens"],
            "latency_ms": round(result["latency_ms"], 1), "cost_usd": round(result["cost_usd"], 6),
            "tool_calls": [tc["name"] for tc in result["tool_calls"]],
        })
        assistant_msg = {"role": "assistant", "content": result["content"]}
        if result["tool_calls"]:
            assistant_msg["tool_calls"] = [
                {"id": tc["id"], "type": "function",
                 "function": {"name": tc["name"], "arguments": tc["arguments"]}}
                for tc in result["tool_calls"]
            ]
        return {
            **state,
            "messages": state["messages"] + [assistant_msg],
            "llm_calls": state["llm_calls"] + 1,
            "tokens": state["tokens"] + result["input_tokens"] + result["output_tokens"],
            "cost_usd": state["cost_usd"] + result["cost_usd"],
        }

    def _tools_node(self, state: AgentState) -> AgentState:
        last = state["messages"][-1]
        new_msgs = list(state["messages"])
        tool_outputs = list(state.get("tool_outputs", []))
        escalation = None
        for tc in last.get("tool_calls", []):
            name = tc["function"]["name"]
            try:
                args = json.loads(tc["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {}
            tool = self.pack.get_tool(name)
            if tool is None or name not in self.allowed or name in ESCALATION_ONLY_ACTIONS:
                result = {"error": f"tool '{name}' is not permitted for role '{self.role}'"}
                audit.record_event(state["session_id"], "tool_call", {
                    "tool": name, "denied": True, "role": self.role})
            elif tool.escalates:
                escalation = {"reason": args.get("reason", ""), "context": args.get("context", ""),
                              "tool": name, "ts": time.time()}
                result = {"status": "escalated_to_human",
                          "detail": "This action requires human approval and has been queued."}
                audit.record_event(state["session_id"], "escalation", escalation)
            else:
                with tracer().start_as_current_span(f"tool:{name}"):
                    try:
                        result = tool.fn(**args)
                    except Exception as e:  # surface tool failures to the model, never crash the run
                        result = {"error": f"{type(e).__name__}: {e}"}
                audit.record_event(state["session_id"], "tool_call",
                                   {"tool": name, "args": args, "ok": "error" not in result})
            result_str = json.dumps(result, default=str)
            tool_outputs.append(result_str)
            new_msgs.append({"role": "tool", "tool_call_id": tc["id"], "content": result_str})
        out = {**state, "messages": new_msgs, "tool_outputs": tool_outputs}
        if escalation:
            out["status"] = "escalated"
            out["escalation"] = escalation
        return out

    def _validate_node(self, state: AgentState) -> AgentState:
        """Runtime self-correction loop: significant figures in the answer must
        trace to tool outputs. On failure the critique is fed back and the
        agent retries with full context; bounded retries, then escalate."""
        answer = state["messages"][-1].get("content") or ""
        claimed = _numbers(answer)
        sourced = set()
        for out in state.get("tool_outputs", []):
            sourced |= _numbers(out)
        unsourced = claimed - sourced
        if unsourced and state.get("tool_outputs"):
            failures = state["validation_failures"] + 1
            audit.record_event(state["session_id"], "validation", {
                "pass": False, "unsourced_figures": sorted(unsourced), "attempt": failures})
            if failures > self.gov.max_validator_retries:
                esc = {"reason": "validation_exhausted",
                       "context": f"figures not traceable to tool outputs: {sorted(unsourced)}",
                       "ts": time.time()}
                audit.record_event(state["session_id"], "escalation", esc)
                return {**state, "status": "escalated", "escalation": esc}
            critique = ("VALIDATOR: these figures do not appear in any tool output: "
                        f"{sorted(unsourced)}. Every significant figure must come from a tool "
                        "result. Re-run the needed tools or correct the figures, then answer again.")
            return {**state,
                    "messages": state["messages"] + [{"role": "user", "content": critique}],
                    "validation_failures": failures}
        audit.record_event(state["session_id"], "validation", {"pass": True})
        red_answer, findings = redact(answer) if self.gov.redaction_enabled else (answer, [])
        if findings:
            audit.record_event(state["session_id"], "redaction",
                               {"direction": "output", "findings": findings})
        return {**state, "status": "completed", "final_answer": red_answer}

    # --- routing -----------------------------------------------------------

    def _route_from_agent(self, state: AgentState) -> str:
        if state.get("status") == "budget_exceeded":
            return "end"
        if state["messages"][-1].get("tool_calls"):
            return "tools"
        return "validate"

    def _route_from_tools(self, state: AgentState) -> str:
        return "end" if state.get("status") == "escalated" else "agent"

    def _route_from_validate(self, state: AgentState) -> str:
        return "end" if state.get("status") in ("completed", "escalated") else "agent"

    def _build(self):
        g = StateGraph(AgentState)
        g.add_node("agent", self._agent_node)
        g.add_node("tools", self._tools_node)
        g.add_node("validate", self._validate_node)
        g.set_entry_point("agent")
        g.add_conditional_edges("agent", self._route_from_agent,
                                {"tools": "tools", "validate": "validate", "end": END})
        g.add_conditional_edges("tools", self._route_from_tools, {"agent": "agent", "end": END})
        g.add_conditional_edges("validate", self._route_from_validate, {"agent": "agent", "end": END})
        return g

    # --- public API ----------------------------------------------------------

    def run_task(self, task: str, task_type: str = "general", session_id: str | None = None) -> dict:
        session_id = session_id or str(uuid.uuid4())
        snap = config_snapshot(self.pack.domain, self.pack.system_prompt,
                               [t.name for t in self.pack.tools], self.role)
        audit.record_snapshot(session_id, self.pack.domain, snap)

        task_clean, findings = redact(task) if self.gov.redaction_enabled else (task, [])
        if findings:
            audit.record_event(session_id, "redaction", {"direction": "input", "findings": findings})

        state: AgentState = {
            "messages": [
                {"role": "system", "content": self.pack.system_prompt},
                {"role": "user", "content": task_clean},
            ],
            "session_id": session_id, "domain": self.pack.domain, "role": self.role,
            "task_type": task_type, "llm_calls": 0, "tokens": 0, "cost_usd": 0.0,
            "validation_failures": 0, "status": "running", "tool_outputs": [],
        }
        t0 = time.perf_counter()
        with SqliteSaver.from_conn_string(CHECKPOINT_DB_PATH) as saver:
            compiled = self.graph.compile(checkpointer=saver)
            final = compiled.invoke(state, config={
                "configurable": {"thread_id": session_id},
                "recursion_limit": 60,
            })
        elapsed = time.perf_counter() - t0

        status = final.get("status", "failed")
        heq = self.pack.task_types.get(task_type, 20.0)
        audit.record_impact(
            task_id=str(uuid.uuid4()), session_id=session_id, domain=self.pack.domain,
            task_type=task_type, completion_seconds=elapsed, human_equivalent_minutes=heq,
            tokens=final.get("tokens", 0), cost_usd=final.get("cost_usd", 0.0),
            escalated=status == "escalated", outcome=status,
        )
        return {
            "session_id": session_id,
            "status": status,
            "answer": final.get("final_answer") or final.get("messages", [{}])[-1].get("content"),
            "escalation": final.get("escalation"),
            "metrics": {
                "llm_calls": final.get("llm_calls", 0),
                "tokens": final.get("tokens", 0),
                "cost_usd": round(final.get("cost_usd", 0.0), 6),
                "latency_seconds": round(elapsed, 2),
                "validation_failures": final.get("validation_failures", 0),
            },
        }
