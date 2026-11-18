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

    def test_seed_replays_earlier_turns_when_given_them(self, tmp_path):
        ws = load_module()
        msg = ws.seed_message("and now?", "DIGEST", "User: ping")
        assert "User: ping" in msg and "DIGEST" in msg


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
        session_id = "b8aff7a7-a46c-4de4-86ec-61085a56ffa1"

        async def runner(msg, session_id):
            calls.append((msg, session_id))
            return {"reply": "ok", "sessionId": session_id or "abc"}

        self.call(monkeypatch, {"message": "hi"}, runner, tmp_path)
        self.call(monkeypatch, {"message": "more", "sessionId": session_id},
                  runner, tmp_path)
        assert calls[-1] == ("more", session_id)  # verbatim: no re-seed

    def test_unresumable_session_id_replays_the_transcript(self, monkeypatch,
                                                           tmp_path):
        """A transcript the CLI cannot --resume must not 502 the user."""
        calls = []
        ws = self.ws
        monkeypatch.setattr(ws, "CHAT_DIR", tmp_path / "chat")
        ws.save_turn("browser-test", "user", "ping")
        ws.save_turn("browser-test", "assistant", "PONG from the test bridge")

        async def runner(msg, session_id):
            calls.append((msg, session_id))
            return {"reply": "PONG", "sessionId":
                    "b8aff7a7-a46c-4de4-86ec-61085a56ffa1"}

        monkeypatch.setattr(ws, "run_claude", runner)
        monkeypatch.setattr(ws, "load_digest", lambda: "DIGEST")
        out = asyncio.run(
            ws.chat(ws.ChatBody(message="why?", sessionId="browser-test")))

        msg, resumed = calls[0]
        assert resumed is None  # never handed to --resume
        assert "DIGEST" in msg
        assert "PONG from the test bridge" in msg  # context kept
        assert "why?" in msg
        assert out["sessionId"] == "browser-test"  # same thread, not a new one
        assert [m["text"] for m in ws.load_chat("browser-test")["messages"]] \
            == ["ping", "PONG from the test bridge", "why?", "PONG"]

    def test_replay_keeps_the_newest_turns_within_the_cap(self, monkeypatch,
                                                          tmp_path):
        ws = self.ws
        monkeypatch.setattr(ws, "CHAT_DIR", tmp_path / "chat")
        monkeypatch.setattr(ws, "REPLAY_MAX_CHARS", 40)
        ws.save_turn("browser-test", "user", "old question " * 10)
        ws.save_turn("browser-test", "assistant", "fresh answer")

        history = ws.history_text("browser-test")
        assert "fresh answer" in history
        assert "old question" not in history

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

    def test_rejects_flag_like_session_id_before_running(self, monkeypatch,
                                                         tmp_path):
        calls = []

        async def runner(msg, session_id):
            calls.append((msg, session_id))
            return {"reply": "x", "sessionId": session_id}

        monkeypatch.setattr(self.ws, "run_claude", runner)
        with pytest.raises(HTTPException) as raised:
            asyncio.run(self.ws.chat(
                self.ws.ChatBody(message="hi", sessionId="--help")))
        assert raised.value.status_code == 400
        assert calls == []


class TestRunClaude:
    class FakeProc:
        def __init__(self, stdout=b"", stderr=b"", code=0, delay=0.0):
            self.stdout, self.stderr, self.code = stdout, stderr, code
            self.returncode = code
            self.delay = delay
            self.pid = 4242
            self.killed = False

        async def communicate(self):
            if self.delay:
                await asyncio.sleep(self.delay)
            return self.stdout, self.stderr

        async def wait(self):
            return self.code

        def kill(self):
            self.killed = True

    def install(self, monkeypatch, proc):
        ws = load_module()

        async def fake_exec(*args, **kwargs):
            return proc

        monkeypatch.setattr(ws.asyncio, "create_subprocess_exec", fake_exec)
        return ws

    def test_missing_cli_is_a_cli_error(self, monkeypatch):
        ws = load_module()

        async def missing(*args, **kwargs):
            raise FileNotFoundError

        monkeypatch.setattr(ws.asyncio, "create_subprocess_exec", missing)
        with pytest.raises(ws.CLIError, match="not found"):
            asyncio.run(ws.run_claude("hi", None))

    def test_nonzero_exit_surfaces_stderr(self, monkeypatch):
        proc = self.FakeProc(stderr=b"bad cli", code=2)
        ws = self.install(monkeypatch, proc)
        with pytest.raises(ws.CLIError, match="bad cli"):
            asyncio.run(ws.run_claude("hi", None))

    def test_unparseable_output_is_a_cli_error(self, monkeypatch):
        proc = self.FakeProc(stdout=b"not json", code=0)
        ws = self.install(monkeypatch, proc)
        with pytest.raises(ws.CLIError, match="unparseable"):
            asyncio.run(ws.run_claude("hi", None))

    def test_timeout_kills_the_process_group(self, monkeypatch):
        proc = self.FakeProc(delay=1.0)
        ws = self.install(monkeypatch, proc)
        killed = []
        monkeypatch.setattr(ws, "TIMEOUT_S", 0.01)
        monkeypatch.setattr(ws.os, "getpgid", lambda pid: pid)
        monkeypatch.setattr(ws.os, "killpg",
                            lambda pgid, sig: killed.append(pgid))
        with pytest.raises(ws.CLIError, match="timed out"):
            asyncio.run(ws.run_claude("hi", None))
        assert killed == [proc.pid]


class TestBodyLimit:
    def request(self, content_length: str | None):
        from starlette.requests import Request
        headers = ([] if content_length is None
                   else [(b"content-length", content_length.encode())])
        return Request({"type": "http", "method": "POST",
                        "path": "/api/chat", "headers": headers})

    def test_oversized_body_is_413(self):
        ws = load_module()
        sentinel = object()

        async def call_next(request):
            return sentinel

        response = asyncio.run(ws.limit_body(
            self.request(str(ws.MAX_BODY_BYTES + 1)), call_next))
        assert response.status_code == 413

    def test_invalid_content_length_is_400(self):
        ws = load_module()

        async def call_next(request):
            return object()

        response = asyncio.run(ws.limit_body(self.request("nope"), call_next))
        assert response.status_code == 400

    def test_normal_request_passes_through(self):
        ws = load_module()
        sentinel = object()

        async def call_next(request):
            return sentinel

        assert asyncio.run(ws.limit_body(self.request("42"), call_next)) is sentinel


class TestDigest:
    def test_reads_the_split_workspace_file(self, monkeypatch, tmp_path):
        ws = load_module()
        snapshot = tmp_path / "snapshot.json"
        snapshot.write_text(json.dumps({
            "generatedAt": "2026-01-01", "counts": {"articles": 2}}))
        (tmp_path / "workspace.json").write_text(json.dumps({
            "runs": [{"slug": "s1", "status": "ok", "netSharpe": 1.2}],
            "failed": [], "specs": [{"slug": "sp"}], "catalogCount": 3}))
        monkeypatch.setattr(ws, "DIGEST_PATH", snapshot)
        digest = ws.load_digest()
        assert "s1" in digest and "3 data series" in digest
