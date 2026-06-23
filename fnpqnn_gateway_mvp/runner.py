"""Process runner and log streamer for gateway hooks.

Security rules:
* commands are argv lists, never shell strings;
* dry-run is available for every runtime hook;
* log output is streamed as process output, but this package never prints stored
  provider secrets because it does not store them.
"""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Iterable

from .codeproject_client import module_probe, status
from .codeproject_mesh import mesh_status
from .hooks import DEFAULT_CODEPROJECT_URL, HookSpec


def _emit(event: dict[str, object], jsonl: bool = False) -> None:
    if jsonl:
        print(json.dumps(event, sort_keys=True))
    else:
        level = event.get("level", "info")
        source = event.get("source", "gateway")
        message = event.get("message", "")
        print(f"[{level}] {source}: {message}")


def dry_run_plan(hook: HookSpec, port: int, host: str, codeproject_url: str, known_servers: list[str]) -> dict[str, object]:
    command = None
    if hook.server_command:
        command = [*hook.server_command, "--port", str(port)]
    return {
        "hook": hook.as_dict(),
        "host": host,
        "port": port,
        "server_command": command,
        "codeproject_url": codeproject_url,
        "known_servers": known_servers,
        "mutates_config": False,
    }


def run_preflight(commands: Iterable[tuple[str, ...]], jsonl: bool = False) -> bool:
    ok = True
    for argv in commands:
        _emit({"source": "preflight", "level": "info", "message": " ".join(argv)}, jsonl=jsonl)
        try:
            proc = subprocess.run(argv, text=True, capture_output=True, timeout=60, check=False)
            ok = ok and proc.returncode == 0
            if proc.stdout:
                _emit({"source": "preflight", "level": "info", "message": proc.stdout[-2000:]}, jsonl=jsonl)
            if proc.stderr:
                _emit({"source": "preflight", "level": "warn", "message": proc.stderr[-2000:]}, jsonl=jsonl)
        except (OSError, subprocess.TimeoutExpired) as exc:
            ok = False
            _emit({"source": "preflight", "level": "warn", "message": f"{type(exc).__name__}: {exc}"}, jsonl=jsonl)
    return ok


def run_hook(
    hook: HookSpec,
    port: int = 8000,
    host: str = "127.0.0.1",
    codeproject_url: str = DEFAULT_CODEPROJECT_URL,
    known_servers: list[str] | None = None,
    jsonl: bool = False,
    dry_run: bool = False,
    no_preflight: bool = False,
) -> int:
    known = known_servers or []
    if dry_run:
        _emit({"source": "dry-run", "level": "info", "message": json.dumps(dry_run_plan(hook, port, host, codeproject_url, known), sort_keys=True)}, jsonl=jsonl)
        return 0
    if hook.codeproject:
        payload = mesh_status(codeproject_url, known_servers=known) if hook.mesh else status(codeproject_url)
        _emit({"source": hook.name, "level": "info", "message": json.dumps(payload, sort_keys=True)}, jsonl=jsonl)
        probe = module_probe(codeproject_url)
        _emit({"source": hook.name, "level": "info", "message": json.dumps(probe, sort_keys=True)}, jsonl=jsonl)
        return 0 if payload.get("success") else 1
    if hook.preflight and not no_preflight:
        run_preflight(hook.preflight, jsonl=jsonl)
    if not hook.server_command:
        _emit({"source": hook.name, "level": "info", "message": "No server command for observe-only hook."}, jsonl=jsonl)
        return 0
    argv = (*hook.server_command, "--port", str(port))
    _emit({"source": hook.name, "level": "info", "message": " ".join(argv)}, jsonl=jsonl)
    proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    assert proc.stdout is not None
    for line in proc.stdout:
        _emit({"source": hook.name, "level": "info", "message": line.rstrip()}, jsonl=jsonl)
    return int(proc.wait())

