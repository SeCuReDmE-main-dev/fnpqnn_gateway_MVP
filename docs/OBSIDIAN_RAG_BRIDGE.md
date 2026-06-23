# Obsidian RAG Bridge

The Obsidian bridge creates a persistent, inspectable memory surface between:

- the selected native tool memory;
- the FNP-QNN gateway state;
- simulator docs and runtime gates.

It does not scrape private tool memory. A native tool must explicitly export or admit a note before it becomes part of the gateway RAG surface.

## Semantics

```text
native tool memory -> explicit export/admission -> Obsidian Markdown note -> JSONL index -> gateway/simulator retrieval
```

LVFM stream:

```text
Obsidian admitted notes -> obsidian-admission-creek -> Cerebrum runtime ingest -> LVFMRuntimeGraph river
```

Ownership:

- Native tool owns its private memory and skills/plugins.
- Gateway owns route selection, gate files, and admitted RAG notes.
- Simulator owns FNP-QNN/Cerebrum logic and runtime endpoints.

## Commands

Create or inspect the vault plan:

```powershell
fnpqnn memory obsidian-init --tool codex --dry-run
fnpqnn memory obsidian-init --tool codex --write
```

Record an admitted memory:

```powershell
fnpqnn memory obsidian-record --tool codex --title "YOLO Cerebrum Gate" --content "Map detections into Cerebrum events." --tag yolo --tag cerebrum --write
```

Query the admitted memory:

```powershell
fnpqnn memory obsidian-query --query "yolo cerebrum"
fnpqnn memory obsidian-lvfm-stream --query "yolo cerebrum"
```

## Files

Default vault:

```text
.fnpqnn_gateway/obsidian_vault
```

The bridge creates:

- `Gateway RAG Home.md`
- `Routes/<tool>.md`
- `Notes/*.md`
- `Admissions/`
- `gateway_rag_index.jsonl`

## Rules

- No raw tokens.
- No provider secret scraping.
- No hidden vector store in v1.
- Markdown notes are the source of truth.
- JSONL index is a retrieval helper.

## LVFM River

The bridge treats admitted notes as a stream that can fill the simulator's LVFM layer. The command:

```powershell
fnpqnn memory obsidian-lvfm-stream --query "yolo lvfm"
```

returns a candidate payload for:

```text
POST /cerebrum/runtime/ingest
POST /cerebrum/runtime/run
```

The gateway does not import `LVFMRuntimeGraph`; it prepares the admitted memory events so the simulator can own LVFM ingestion.
