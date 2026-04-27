from __future__ import annotations

import asyncio
import importlib
import sys
import types
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "skills" / "parsidion" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

SUMMARIZE_SESSIONS_PATH = SCRIPTS_DIR / "summarize_sessions.py"


def test_summarize_sessions_source_uses_ai_backend_not_claude_agent_sdk() -> None:
    source = SUMMARIZE_SESSIONS_PATH.read_text(encoding="utf-8")

    assert "claude-agent-sdk" not in source
    assert "claude_agent_sdk" not in source
    assert "import ai_backend" in source


def test_summarizer_config_models_accept_none() -> None:
    import vault_config

    assert vault_config._CONFIG_SCHEMA["summarizer"]["model"] == (str, type(None))
    assert vault_config._CONFIG_SCHEMA["summarizer"]["cluster_model"] == (
        str,
        type(None),
    )


class _FakeSemaphore:
    def __init__(self, _: int = 1) -> None:
        pass

    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *args: object) -> None:
        return None


def _fresh_summarize_sessions(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    monkeypatch.setitem(
        sys.modules,
        "anyio",
        types.SimpleNamespace(
            Semaphore=_FakeSemaphore,
            to_thread=types.SimpleNamespace(run_sync=lambda func, *args: func(*args)),
        ),
    )
    sys.modules.pop("summarize_sessions", None)
    return importlib.import_module("summarize_sessions")


def test_run_summarizer_prompt_delegates_to_ai_backend_in_thread(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    thread_calls: list[object] = []

    async def fake_run_sync(func: object, *args: object) -> object:
        thread_calls.append(func)
        assert callable(func)
        return func(*args)

    monkeypatch.setitem(
        sys.modules,
        "anyio",
        types.SimpleNamespace(
            Semaphore=object,
            to_thread=types.SimpleNamespace(run_sync=fake_run_sync),
        ),
    )
    sys.modules.pop("summarize_sessions", None)
    summarize_sessions = importlib.import_module("summarize_sessions")
    calls: list[dict[str, object]] = []

    def fake_run_ai_prompt(prompt: str, **kwargs: object) -> str:
        calls.append({"prompt": prompt, **kwargs})
        return "summary text"

    monkeypatch.setattr(
        summarize_sessions.ai_backend, "run_ai_prompt", fake_run_ai_prompt
    )

    result = asyncio.run(
        summarize_sessions._run_summarizer_prompt(
            "prompt text",
            model="model-id",
            model_tier="large",
            purpose="session-summary",
            timeout=123,
            vault=tmp_path,
        )
    )

    assert result == "summary text"
    assert len(thread_calls) == 1
    assert calls == [
        {
            "prompt": "prompt text",
            "model": "model-id",
            "model_tier": "large",
            "purpose": "session-summary",
            "timeout": 123,
            "vault": tmp_path,
        }
    ]


def test_summarize_chunk_returns_backend_output_when_prompt_runner_is_patched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    summarize_sessions = _fresh_summarize_sessions(monkeypatch)
    calls: list[dict[str, object]] = []

    async def fake_run_summarizer_prompt(prompt: str, **kwargs: object) -> str:
        calls.append({"prompt": prompt, **kwargs})
        return "backend summary"

    monkeypatch.setattr(
        summarize_sessions, "_run_summarizer_prompt", fake_run_summarizer_prompt
    )

    result = asyncio.run(
        summarize_sessions._summarize_chunk(
            "chunk body", 2, 3, "chunk-model", {"no-session-persistence": None}
        )
    )

    assert result == "backend summary"
    assert len(calls) == 1
    assert "portion (2/3)" in str(calls[0]["prompt"])
    assert calls[0]["model"] == "chunk-model"


def test_summarize_one_uses_backend_skip_decision_when_prompt_runner_is_patched(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    summarize_sessions = _fresh_summarize_sessions(monkeypatch)
    transcript_path = tmp_path / "session.jsonl"
    transcript_path.write_text(
        '{"type":"user","content":"Investigate a routine issue"}\n'
        '{"type":"assistant","content":"Ran checks and found nothing reusable"}\n',
        encoding="utf-8",
    )
    calls: list[dict[str, object]] = []

    async def fake_run_summarizer_prompt(prompt: str, **kwargs: object) -> str:
        calls.append({"prompt": prompt, **kwargs})
        return '{"decision": "skip", "reason": "routine transient session"}'

    monkeypatch.setattr(
        summarize_sessions, "_run_summarizer_prompt", fake_run_summarizer_prompt
    )
    monkeypatch.setattr(
        summarize_sessions, "_find_dedup_candidates", lambda *a, **k: []
    )

    async def run() -> tuple[dict[str, object], Path | str | None]:
        return await summarize_sessions.summarize_one(
            {
                "transcript_path": str(transcript_path),
                "project": "parsidion",
                "categories": ["testing"],
                "session_id": "session-1234",
            },
            "summary-model",
            True,
            summarize_sessions.anyio.Semaphore(1),
            ["testing"],
            False,
            tmp_path / "vault",
        )

    entry, written = asyncio.run(run())

    assert entry["session_id"] == "session-1234"
    assert written is None
    assert len(calls) == 1
    assert calls[0]["model"] == "summary-model"
    assert "session-1234" in str(calls[0]["prompt"])
