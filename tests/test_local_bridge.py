"""Tests for local_bridge.py — the local CLI chat bridge. The claude CLI is
never invoked in tests; only arg/parse/format logic and the FastAPI handlers
with the runner monkeypatched."""
import asyncio
import importlib.util
import json
from pathlib import Path

from fastapi import HTTPException

ROOT = Path(__file__).resolve().parent.parent


def load_module():
    spec = importlib.util.spec_from_file_location(
        "local_bridge", ROOT / "local_bridge.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestArgs:
    def test_first_message_has_no_resume(self):
        ws = load_module()
        args = ws.build_claude_args("hello", None)
        assert args == ["-p", "hello", "--output-format", "json"]

    def test_resume_appends_session_flag(self):
        ws = load_module()
        args = ws.build_claude_args("follow-up", "abc-123")
        assert args[:2] == ["--resume", "abc-123"]
        assert "-p" in args and "follow-up" in args
        assert args[-1] == "json"


class TestParse:
    def test_valid_json_reply(self):
        ws = load_module()
        out = json.dumps({"result": "PONG", "session_id": "abc"})
        assert ws.parse_reply(out) == {"reply": "PONG", "sessionId": "abc"}

    def test_error_flag_raises(self):
        ws = load_module()
        out = json.dumps({"result": "", "is_error": True, "result": "boom"})
        import pytest
        with pytest.raises(ws.CLIError, match="boom"):
            ws.parse_reply(out)

    def test_torn_output_raises(self):
        ws = load_module()
        import pytest
        with pytest.raises(ws.CLIError):
            ws.parse_reply("not json at all")


class TestSeedContext:
    def test_first_message_embeds_digest(self, tmp_path):
        ws = load_module()
        digest = "ARTIFACT COUNTS: 151 articles"
        msg = ws.seed_message("how many runs?", digest)
        assert digest in msg and "how many runs?" in msg

    def test_seed_wraps_message(self, tmp_path):
        ws = load_module()
        msg = ws.seed_message("how many runs?", "DIGEST")
        assert "how many runs?" in msg and "DIGEST" in msg


class TestAPI:
    """Handlers called directly (no HTTP layer) with the runner monkeypatched."""

    def setup_method(self):
        self.ws = load_module()

    def call(self, monkeypatch, body, runner):
        monkeypatch.setattr(self.ws, "run_claude", runner)
        monkeypatch.setattr(self.ws, "load_digest", lambda: "DIGEST")
        return asyncio.run(self.ws.chat(self.ws.ChatBody(**body)))

    def test_chat_roundtrip(self, monkeypatch):
        calls = []

        async def runner(msg, session_id):
            calls.append((msg, session_id))
            return {"reply": "PONG", "sessionId": "abc"}

        out = self.call(monkeypatch, {"message": "hi"}, runner)
        assert out == {"reply": "PONG", "sessionId": "abc"}
        assert calls[0][1] is None  # first turn: no resume
        assert "DIGEST" in calls[0][0] and "hi" in calls[0][0]  # seeded

    def test_second_turn_resumes_session_verbatim(self, monkeypatch):
        calls = []

        async def runner(msg, session_id):
            calls.append((msg, session_id))
            return {"reply": "ok", "sessionId": session_id or "abc"}

        self.call(monkeypatch, {"message": "hi"}, runner)
        self.call(monkeypatch, {"message": "more", "sessionId": "abc"}, runner)
        assert calls[-1] == ("more", "abc")  # verbatim: no re-seed, resumed

    def test_cli_failure_maps_to_502(self, monkeypatch):
        async def runner(msg, session_id):
            raise self.ws.CLIError("boom from cli")
        try:
            self.call(monkeypatch, {"message": "hi"}, runner)
            raised = None
        except HTTPException as exc:
            raised = exc
        assert raised is not None and raised.status_code == 502
        assert "boom" in raised.detail

    def test_rejects_empty_message(self, monkeypatch):
        try:
            self.call(monkeypatch, {"message": "   "}, lambda *a: {})
            raised = None
        except HTTPException as exc:
            raised = exc
        assert raised is not None and raised.status_code == 400
