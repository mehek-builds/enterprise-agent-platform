"""Domain pack contract. A pack is a directory under app/packs/<domain>/ with:

  system_prompt.md   role definition, function scope, escalation rules
  tools.py           exposes TOOLS: list[Tool] and TASK_TYPES: dict
  dataset/           synthetic structured data (JSON)
  golden_tasks.json  eval suite: scenario, prompt, oracle answer, pass criteria

The chassis is domain-agnostic; everything domain-specific lives in the pack.
"""
import importlib
import json
import os
from dataclasses import dataclass, field
from typing import Callable

PACKS_DIR = os.path.dirname(__file__)


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict                      # JSON schema for arguments
    fn: Callable[..., dict]               # returns a JSON-serializable result
    human_equivalent_minutes: float = 15  # documented impact assumption per call
    escalates: bool = False               # True for the escalate() gate itself


@dataclass
class DomainPack:
    domain: str
    system_prompt: str
    tools: list[Tool]
    task_types: dict[str, float]          # task_type -> human-equivalent minutes
    path: str = ""

    def tool_schemas(self, allowed: set[str]) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {"name": t.name, "description": t.description, "parameters": t.parameters},
            }
            for t in self.tools
            if t.name in allowed
        ]

    def get_tool(self, name: str) -> Tool | None:
        return next((t for t in self.tools if t.name == name), None)


def load_pack(domain: str) -> DomainPack:
    pack_dir = os.path.join(PACKS_DIR, domain)
    with open(os.path.join(pack_dir, "system_prompt.md")) as f:
        system_prompt = f.read()
    mod = importlib.import_module(f"app.packs.{domain}.tools")
    return DomainPack(
        domain=domain,
        system_prompt=system_prompt,
        tools=mod.TOOLS,
        task_types=getattr(mod, "TASK_TYPES", {}),
        path=pack_dir,
    )


def list_packs() -> list[str]:
    return sorted(
        d for d in os.listdir(PACKS_DIR)
        if os.path.isdir(os.path.join(PACKS_DIR, d))
        and os.path.exists(os.path.join(PACKS_DIR, d, "system_prompt.md"))
    )


def load_dataset(pack_path: str, name: str):
    with open(os.path.join(pack_path, "dataset", name)) as f:
        return json.load(f)
