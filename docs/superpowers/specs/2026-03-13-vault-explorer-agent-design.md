# Vault Explorer Agent — Design Spec

**Date:** 2026-03-13
**Status:** Approved

---

## Problem

Every vault search runs inside the main Claude session's context window. A typical lookup involves multiple Grep calls across vault subfolders, followed by several Read calls for matching files. This consumes context budget on search mechanics rather than on the actual work the user requested.

---

## Solution

A dedicated `vault-explorer` subagent (Haiku model) that accepts a natural language query, performs all Grep/Read work in its own context, and returns a compact two-section result to the main session. The main session's context grows by one agent result block instead of N Grep results + M Read results.

**Escalation chain:**
vault-explorer → (no results) → research-documentation-agent → saves findings to vault

---

## Components

### 1. `agents/vault-explorer.md`

- **Model:** `claude-haiku-4-5-20251001`
- **Color:** `purple`
- **Role:** Read-only vault search specialist. No writes, no index rebuilds.

**Behaviour:**
1. Check `~/ClaudeVault/CLAUDE.md` index to orient on available notes.
2. Extract key signals from the query (error class, package name, feature keyword).
3. Run targeted Grep searches across relevant subfolders: `Debugging/`, `Patterns/`, `Frameworks/`, `Languages/`, `Projects/`, `Research/`, `Tools/`.
4. Read the top matching files (up to 5, ranked by relevance).
5. Synthesize and return in the standard two-section format.

**Return format:**
```
## Answer
[Direct synthesized answer to the query — 3-7 sentences.
 "No relevant vault notes found." if nothing matches.]

## Sources
- ~/ClaudeVault/Debugging/foo.md — one-line relevance note
- ~/ClaudeVault/Patterns/retry-pattern.md — one-line relevance note
```

**No-match response:**
> "No relevant vault notes found. Recommend dispatching the `research-documentation-agent` to research this topic externally and save findings to the vault."

**Folder search strategy** (baked into the agent's instructions):

| Query type | Folders searched first |
|---|---|
| Error / exception / bug | `Debugging/` → `Frameworks/` → `Languages/` |
| Feature / pattern / integration | `Patterns/` → `Frameworks/` → `Projects/` |
| Cross-project / prior art | `Projects/` → `Patterns/` |
| Library / tool / CLI | `Tools/` → `Frameworks/` |
| Research / concepts | `Research/` → all |

---

### 2. `CLAUDE-VAULT.md` — updated search guidance

**Debugging section** — step 2 changes from:
> Search `~/ClaudeVault/Debugging/` first with Grep

To:
> Dispatch the `vault-explorer` agent with the error signal as the query.

**Implementation section** — step 1-3 changes from:
> Search `Patterns/`, `Frameworks/`, `Projects/` with Grep

To:
> Dispatch the `vault-explorer` agent with the feature keyword as the query.

**"Efficient Vault Search" section** replaces the Grep table with:
> Dispatch the `vault-explorer` agent with a natural language query.
> - **Answer returned?** Proceed. `Read` specific source files only if you need more depth than the Answer section provides.
> - **"No relevant vault notes found"?** Dispatch the `research-documentation-agent` for external research.

The Grep strategy table moves inside the vault-explorer agent's own instructions.

---

### 3. `skills/claude-vault/SKILL.md` — updated search guidance

Same changes as CLAUDE-VAULT.md: the "Efficient Vault Search" table and the Grep examples in the Debugging/Implementation sections are replaced with vault-explorer agent dispatch instructions.

---

### 4. `install.py` — multi-agent support

`AGENT_SRC: Path` → `AGENT_SRCS: list[Path]`:

```python
AGENT_SRCS: list[Path] = [
    REPO_ROOT / "agents" / "research-documentation-agent.md",
    REPO_ROOT / "agents" / "vault-explorer.md",
]
```

- `install_agent()` → `install_agents()`: iterates the list, copies each to `~/.claude/agents/`
- `--skip-agent` flag skips all agents
- Uninstall removes all listed agents
- Summary printout lists both installed agents

---

## Files Changed

| File | Change type |
|---|---|
| `agents/vault-explorer.md` | **New** |
| `CLAUDE-VAULT.md` | Updated — search guidance |
| `skills/claude-vault/SKILL.md` | Updated — search guidance |
| `install.py` | Updated — multi-agent support |

---

## Out of Scope

- The vault-explorer agent does not write notes, save findings, or rebuild the index.
- The vault-explorer agent does not replace the `session_start_hook.py` AI selection mode.
- No changes to hook scripts, summarizer, or vault structure.
