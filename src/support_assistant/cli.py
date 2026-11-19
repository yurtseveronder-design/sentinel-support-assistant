from __future__ import annotations

import argparse
import os
from pathlib import Path

from .assistant import Assistant
from .guard import HttpGuard, LocalGuard, NoGuard
from .llm import GullibleModel


def build(root: Path, guard: str, model: str) -> Assistant:
    if guard == "sentinel":
        g = HttpGuard(os.environ.get("SENTINEL_URL", "http://localhost:8000"), os.environ.get("SENTINEL_API_KEY", "change-me"))
    elif guard == "local":
        g = LocalGuard()
    else:
        g = NoGuard()
    m = GullibleModel() if model == "gullible" else None
    return Assistant(root, g, m)


def main(argv=None):
    p = argparse.ArgumentParser(prog="ssa")
    p.add_argument("question")
    p.add_argument("--root", default=".")
    p.add_argument("--guard", choices=["none", "local", "sentinel"], default="none")
    p.add_argument("--model", choices=["extractive", "gullible"], default="extractive")
    a = p.parse_args(argv)
    r = build(Path(a.root), a.guard, a.model).ask(a.question)
    print(r.text)
    print(f"[status={r.status} sources={r.sources} quarantined={r.quarantined}]")


if __name__ == "__main__":
    main()
