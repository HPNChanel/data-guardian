from __future__ import annotations

import json
from pathlib import Path
from typing import List

from ..storage.paths import PathResolver


def resolve_recipients(entries: List[str]) -> List[str]:
    """Resolve recipient spec list into KIDs, supporting groups/roles.

    Reads optional policy file at <store>/meta/recipients.json:
    {
        "groups": {"eng": ["rsa_abc", "x25519_def"]},
        "roles": {"admin": ["rsa_xyz"]}
    }
    """
    pr = PathResolver()
    policy_path = pr.meta / "recipients.json"
    groups = {}
    roles = {}
    if policy_path.exists():
        data = json.loads(policy_path.read_text(encoding="utf-8"))
        groups = data.get("groups", {})
        roles = data.get("roles", {})

    out: list[str] = []
    for e in entries:
        if e.startswith("group:"):
            out.extend(groups.get(e.split(":",1)[1], []))
        elif e.startswith("role:"):
            out.extend(roles.get(e.split(":",1)[1], []))
        else:
            out.append(e)
    # de-duplicate while preserving order
    seen = set()
    result = []
    for k in out:
        if k not in seen:
            result.append(k); seen.add(k)
    return result

