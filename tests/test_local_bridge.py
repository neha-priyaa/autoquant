"""Tests for local_bridge.py — the local CLI chat bridge. The claude CLI is
never invoked in tests; only arg/parse/format logic and the FastAPI handlers
with the runner monkeypatched."""
import asyncio
import importlib.util
import json
from pathlib import Path

import pytest
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
        out = json.dumps({"result": "boom", "is_error": True})
        with pytest.raises(ws.CLIError, match="boom"):
            ws.parse_reply(out)

    def test_torn_output_raises(self):
        ws = load_module()
        with pytest.raises(ws.CLIError):
            ws.parse_reply("not json at all")


class TestHistory:
    """Transcripts persisted inside the repo workspace (data/chat)."""

    def store(self, monkeypatch, tmp_path):
        ws = load_module()
        monkeypatch.setattr(ws, "CHAT_DIR", tmp_path / "chat")
        return ws

    def test_turns_are_saved_with_a_title_from_the_question(
            self, monkeypatch, tmp_path):
        ws = self.store(monkeypatch, tmp_path)
        ws.save_turn("abc", "user", "how many runs?")
        ws.save_turn("abc", "assistant", "7 backtests")
        chat = ws.load_chat("abc")
        assert chat["title"] == "how many runs?"
        assert [m["role"] for m in chat["messages"]] == [
            "user", "assistant"]
        assert chat["messages"][1]["text"] == "7 backtests"

    def test_long_question_is_truncated_for_the_title(
            self, monkeypatch, tmp_path):
        ws = self.store(monkeypatch, tmp_path)
        ws.save_turn("abc", "user", "x" * 200)
        assert ws.load_chat("abc")["title"] == "x" * ws.TITLE_MAX

    def test_chats_are_listed_newest_first(self, monkeypatch, tmp_path):
        ws = self.store(monkeypatch, tmp_path)
        for sid, at in (("old", "2026-01-01T00:00:00+00:00"),
                        ("new", "2026-01-02T00:00:00+00:00")):
            path = ws.CHAT_DIR / f"{sid}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({
                "sessionId": sid, "title": sid, "updated": at,
                "messages": [{"role": "user", "text": "q"}]}))
        assert [c["sessionId"] for c in ws.list_chats()] == ["new", "old"]
        assert ws.list_chats()[0]["messageCount"] == 1

    def test_empty_store_lists_nothing(self, monkeypatch, tmp_path):
        ws = self.store(monkeypatch, tmp_path)
        assert ws.list_chats() == []

    def test_unknown_chat_is_none(self, monkeypatch, tmp_path):
        ws = self.store(monkeypatch, tmp_path)
        assert ws.load_chat("missing") is None

    def test_unsafe_session_id_is_rejected(self, monkeypatch, tmp_path):
        ws = self.store(monkeypatch, tmp_path)
        with pytest.raises(ValueError):
            ws.save_turn("../../escape", "user", "hi")

    def test_corrupt_file_is_skipped_in_the_list(
            self, monkeypatch, tmp_path):
        ws = self.store(monkeypatch, tmp_path)
        ws.CHAT_DIR.mkdir(parents=True)
        (ws.CHAT_DIR / "bad.json").write_text("{not json")
        assert ws.list_chats() == []


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

    def call(self, monkeypatch, body, runner, tmp_path):
        monkeypatch.setattr(self.ws, "CHAT_DIR", tmp_path / "chat")
        monkeypatch.setattr(self.ws, "run_claude", runner)
        monkeypatch.setattr(self.ws, "load_digest", lambda: "DIGEST")
        return asyncio.run(self.ws.chat(self.ws.ChatBody(**body)))

    def test_chat_roundtrip(self, monkeypatch, tmp_path):
        calls = []

        async def runner(msg, session_id):
            calls.append((msg, session_id))
            return {"reply": "PONG", "sessionId": "abc"}

        out = self.call(monkeypatch, {"message": "hi"}, runner, tmp_path)
        assert out == {"reply": "PONG", "sessionId": "abc"}
        assert calls[0][1] is None  # first turn: no resume
        assert "DIGEST" in calls[0][0] and "hi" in calls[0][0]  # seeded

    def test_transcript_saves_the_question_without_the_digest(
            self, monkeypatch, tmp_path):
        async def runner(msg, session_id):
            return {"reply": "PONG", "sessionId": "abc"}

        self.call(monkeypatch, {"message": "hi"}, runner, tmp_path)
        chat = self.ws.load_chat("abc")
        assert [m["text"] for m in chat["messages"]] == ["hi", "PONG"]
        assert chat["title"] == "hi"

    def test_history_failure_does_not_lose_the_reply(
            self, monkeypatch, tmp_path):
        async def runner(msg, session_id):
            return {"reply": "PONG", "sessionId": "abc"}

        monkeypatch.setattr(self.ws, "CHAT_DIR", tmp_path / "chat")
        monkeypatch.setattr(self.ws, "run_claude", runner)
        monkeypatch.setattr(self.ws, "load_digest", lambda: "DIGEST")

        def broken(*args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr(self.ws, "save_turn", broken)
        out = asyncio.run(self.ws.chat(self.ws.ChatBody(message="hi")))
        assert out == {"reply": "PONG", "sessionId": "abc"}

    def test_chats_endpoint_lists_saved_conversations(
            self, monkeypatch, tmp_path):
        ws = self.ws
        monkeypatch.setattr(ws, "CHAT_DIR", tmp_path / "chat")
        ws.save_turn("abc", "user", "hi")
        ws.save_turn("abc", "assistant", "PONG")
        assert [c["sessionId"] for c in ws.chats()] == ["abc"]

    def test_chat_transcript_endpoint(self, monkeypatch, tmp_path):
        ws = self.ws
        monkeypatch.setattr(ws, "CHAT_DIR", tmp_path / "chat")
        ws.save_turn("abc", "user", "hi")
        assert [m["text"] for m in ws.chat_transcript("abc")["messages"]] \
            == ["hi"]

    def test_unknown_transcript_is_404(self, monkeypatch, tmp_path):
        monkeypatch.setattr(self.ws, "CHAT_DIR", tmp_path / "chat")
        with pytest.raises(HTTPException) as raised:
            self.ws.chat_transcript("missing")
        assert raised.value.status_code == 404

    def test_unsafe_transcript_id_is_400(self, monkeypatch, tmp_path):
        monkeypatch.setattr(self.ws, "CHAT_DIR", tmp_path / "chat")
        with pytest.raises(HTTPException) as raised:
            self.ws.chat_transcript("../../etc/passwd")
        assert raised.value.status_code == 400

    def test_second_turn_resumes_session_verbatim(self, monkeypatch,
                                                  tmp_path):
        calls = []

        async def runner(msg, session_id):
            calls.append((msg, session_id))
            return {"reply": "ok", "sessionId": session_id or "abc"}

        self.call(monkeypatch, {"message": "hi"}, runner, tmp_path)
        self.call(monkeypatch, {"message": "more", "sessionId": "abc"},
                  runner, tmp_path)
        assert calls[-1] == ("more", "abc")  # verbatim: no re-seed, resumed

    def test_cli_failure_maps_to_502(self, monkeypatch, tmp_path):
        async def runner(msg, session_id):
            raise self.ws.CLIError("boom from cli")
        with pytest.raises(HTTPException) as raised:
            self.call(monkeypatch, {"message": "hi"}, runner, tmp_path)
        assert raised.value.status_code == 502
        assert "boom" in raised.value.detail

    def test_rejects_empty_message(self, monkeypatch, tmp_path):
        with pytest.raises(HTTPException) as raised:
            self.call(monkeypatch, {"message": "   "}, lambda *a: {},
                      tmp_path)
        assert raised.value.status_code == 400
