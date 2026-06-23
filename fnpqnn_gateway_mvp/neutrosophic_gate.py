"""Neutrosophic admission gates for gateway memory.

The gateway uses p114 as a transport/admission signal. It does not make
provider memory authoritative and it does not replace the simulator's LVFM
logic; it only tags admitted notes with bounded T/I/F metadata.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import Any, Iterable, Mapping


P114_PLUGIN_ID = "p114_ffed_neutrosophic_consensus"
DEFAULT_PLUGINPACK_PATH = Path(os.getenv("FNP_QNN_FFED_PLUGINPACK_PATH", r"C:\Users\jeans\Desktop\pluginpack"))


def p114_items_from_note(title: str, content: str, tags: Iterable[str] | None = None, source: str = "gateway-note") -> list[dict[str, Any]]:
    return [
        {"label": title[:120], "text": content[:4000]},
        {"label": "source", "text": f"source evidence {source}"},
        {"label": "tags", "text": " ".join(tags or [])},
    ]


def p114_consensus(
    items: Iterable[Any],
    *,
    mode: str = "score_evidence",
    thresholds: Mapping[str, Any] | None = None,
    pluginpack_path: str | Path | None = None,
) -> dict[str, Any]:
    pluginpack = Path(pluginpack_path) if pluginpack_path is not None else DEFAULT_PLUGINPACK_PATH
    if not pluginpack.exists():
        return _gate_payload(
            {
                "status": "disabled",
                "plugin_id": P114_PLUGIN_ID,
                "outputs": {},
                "metrics": {},
                "metadata": {"message": "pluginpack path not found", "pluginpack_path": str(pluginpack)},
            }
        )
    try:
        pluginpack_text = str(pluginpack)
        if pluginpack_text not in sys.path:
            sys.path.insert(0, pluginpack_text)
        from ffed_runtime import run_plugin  # type: ignore
    except Exception as exc:
        return _gate_payload(
            {
                "status": "disabled",
                "plugin_id": P114_PLUGIN_ID,
                "outputs": {},
                "metrics": {},
                "metadata": {"message": f"plugin runtime import failed: {exc}", "pluginpack_path": str(pluginpack)},
            }
        )
    config: dict[str, Any] = {"mode": mode, "items": list(items)[:100]}
    if thresholds:
        config["thresholds"] = dict(thresholds)
    try:
        result = run_plugin(P114_PLUGIN_ID, config)
    except Exception as exc:
        result = {
            "status": "error",
            "plugin_id": P114_PLUGIN_ID,
            "outputs": {},
            "metrics": {},
            "metadata": {"message": str(exc), "mode": mode},
        }
    payload = _gate_payload(result)
    payload["effective_config"] = config
    return payload


def _gate_payload(result: Mapping[str, Any]) -> dict[str, Any]:
    outputs = dict(result.get("outputs") or {})
    metrics = dict(result.get("metrics") or {})
    consensus = dict(outputs.get("consensus") or {})
    truth = _clamp01(consensus.get("truth", metrics.get("truth")))
    indeterminacy = _clamp01(consensus.get("indeterminacy", metrics.get("indeterminacy", 1.0)))
    falsity = _clamp01(consensus.get("falsity", metrics.get("falsity")))
    action = str(outputs.get("action") or _action(truth, indeterminacy, falsity))
    return {
        "success": result.get("status") == "success",
        "status": result.get("status", "error"),
        "plugin_id": P114_PLUGIN_ID,
        "consensus": {"truth": truth, "indeterminacy": indeterminacy, "falsity": falsity},
        "action": action,
        "explanation": outputs.get("explanation") or _reason(action),
        "items": outputs.get("items", []),
        "cli_gate": _cli_gate(action),
        "metadata": dict(result.get("metadata") or {}),
        "raw_token_stored": False,
        "hierarchy": "I -> I_system^S -> D_f -> dF -> i_fractal",
    }


def _clamp01(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = 0.0
    return min(1.0, max(0.0, numeric))


def _action(truth: float, indeterminacy: float, falsity: float) -> str:
    if indeterminacy > 0.6:
        return "ask_clarification"
    if falsity > 0.5:
        return "escalate_or_reject"
    if truth > 0.7:
        return "respond_with_confidence"
    return "respond_with_caveat"


def _cli_gate(action: str) -> dict[str, Any]:
    if action == "ask_clarification":
        return {"status": "needs_clarification", "allow_lvfm_admission": False}
    if action == "escalate_or_reject":
        return {"status": "blocked", "allow_lvfm_admission": False}
    if action == "respond_with_confidence":
        return {"status": "accepted", "allow_lvfm_admission": True}
    return {"status": "accepted_with_caveat", "allow_lvfm_admission": True}


def _reason(action: str) -> str:
    if action == "ask_clarification":
        return "Indeterminacy is high; request more evidence before admitting to LVFM."
    if action == "escalate_or_reject":
        return "Falsity is high; block or escalate the admission."
    if action == "respond_with_confidence":
        return "Truth is high; admit with confidence while preserving provenance."
    return "No blocking threshold crossed; admit with explicit caveats."
