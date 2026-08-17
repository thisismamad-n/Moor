"""Tests for the bundled observability/nemo_relay plugin."""

from __future__ import annotations

import asyncio
import contextvars
import gc
import importlib
import json
import sys
import warnings
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from hermes_cli import lifecycle, plugins as plugin_api
from hermes_cli.observability import relay_runtime, relay_shared_metrics
from hermes_cli.plugins import PluginManager


REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_DIR = REPO_ROOT / "plugins" / "observability" / "nemo_relay"


class _FakeNemoRelay:
    def __init__(self):
        self.events = []
        self._callbacks = {}
        self._llm_starts = {}
        self._scope_serial = 0
        self._scope_context = contextvars.ContextVar(
            "fake_nemo_relay_scope", default=None
        )
        self.ScopeType = SimpleNamespace(Agent="agent", Function="function")
        self.scope = SimpleNamespace(
            push=self._scope_push,
            pop=self._scope_pop,
            event=self._scope_event,
        )
        self.llm = SimpleNamespace(
            call=self._llm_call,
            call_end=self._llm_call_end,
            execute=self._llm_execute,
        )
        self.tools = SimpleNamespace(
            call=self._tool_call,
            call_end=self._tool_call_end,
            execute=self._tool_execute,
            request_intercepts=self._tool_request_intercepts,
        )
        self.plugin = SimpleNamespace(
            initialize=self._plugin_initialize,
            clear=self._plugin_clear,
            initialize_with_dynamic_plugins=self._plugin_initialize_with_dynamic,
        )
        self.subscribers = SimpleNamespace(
            register=self._register_subscriber,
            deregister=self._deregister_subscriber,
            flush=self._flush_subscribers,
        )
        self.LLMRequest = _FakeLLMRequest
        self.AtofExporterConfig = _FakeAtofExporterConfig
        self.AtofExporterMode = SimpleNamespace(Append="append", Overwrite="overwrite")
        self.AtofExporter = self._make_atof_exporter
        self.AtifExporter = self._make_atif_exporter
        self.get_scope_stack = self._get_scope_stack

    def _scope_push(self, name, scope_type, **kwargs):
        self._scope_serial += 1
        handle = ("scope", name, self._scope_serial)
        self._scope_context.set(handle)
        self.events.append(("scope.push", name, scope_type, kwargs))
        return handle

    def _scope_pop(self, handle, **kwargs):
        self.events.append(("scope.pop", handle, kwargs))

    def _scope_event(self, name, **kwargs):
        self.events.append(("scope.event", name, kwargs))

    def _get_scope_stack(self):
        current = self._scope_context.get()
        self.events.append(("scope.sync", current))
        return current

    def _llm_call(self, name, request, **kwargs):
        handle = ("llm", name)
        self._llm_starts[handle] = kwargs
        self.events.append(("llm.call", name, request.content, kwargs))
        return handle

    def _llm_call_end(self, handle, response, **kwargs):
        self.events.append(("llm.call_end", handle, response, kwargs))
        start = self._llm_starts.pop(handle, {})
        event = SimpleNamespace(
            kind="scope",
            category="llm",
            name=handle[1],
            scope_category="end",
            category_profile={"model_name": start.get("model_name")},
            metadata={
                **(start.get("metadata") or {}),
                **(kwargs.get("metadata") or {}),
                "otel.status_code": "OK",
            },
            data=response,
        )
        for callback in list(self._callbacks.values()):
            callback(event)

    def _llm_execute(self, name, request, func, **kwargs):
        self.events.append(("llm.execute.start", name, request.content, kwargs))
        handle = self._llm_call(name, request, **kwargs)
        result = func(_FakeLLMRequest(request.headers, {"intercepted": True, **request.content}))
        self._llm_call_end(
            handle,
            result,
            **{key: value for key, value in kwargs.items() if key != "handle"},
        )
        self.events.append(("llm.execute.end", name, result, kwargs))
        return result

    def _tool_call(self, name, args, **kwargs):
        handle = ("tool", name)
        self.events.append(("tool.call", name, args, kwargs))
        return handle

    def _tool_call_end(self, handle, result, **kwargs):
        self.events.append(("tool.call_end", handle, result, kwargs))

    def _tool_execute(self, name, args, func, **kwargs):
        self.events.append(("tool.execute.start", name, args, kwargs))
        handle = self._tool_call(name, args, **kwargs)
        result = func(args)
        self._tool_call_end(
            handle,
            result,
            **{key: value for key, value in kwargs.items() if key != "handle"},
        )
        self.events.append(("tool.execute.end", name, result, kwargs))
        return result

    def _tool_request_intercepts(self, name, args):
        self.events.append(("tool.request_intercepts", name, args))
        return {"intercepted": True, **args}

    def _make_atof_exporter(self, config):
        return _FakeAtofExporter(self.events, config)

    def _make_atif_exporter(self, session_id, agent_name, agent_version, **kwargs):
        return _FakeAtifExporter(self.events, session_id, agent_name, agent_version, kwargs)

    async def _plugin_initialize(self, config):
        self.events.append(("plugin.initialize", config))
        return {"diagnostics": []}

    async def _plugin_clear(self):
        self.events.append(("plugin.clear",))

    async def _plugin_initialize_with_dynamic(self, config, dynamic_plugins):
        self.events.append(("plugin.activate_dynamic", config, dynamic_plugins))
        return _FakePluginActivation(self.events)

    def _register_subscriber(self, name, callback):
        self._callbacks[name] = callback
        self.events.append(("subscribers.register", name))

    def _deregister_subscriber(self, name):
        self._callbacks.pop(name, None)
        self.events.append(("subscribers.deregister", name))

    def _flush_subscribers(self):
        self.events.append(("subscribers.flush",))


class _FakePluginActivation:
    def __init__(self, events):
        self.events = events
        self.report = {"diagnostics": []}

    async def close(self):
        self.events.append(("plugin.activation.close",))


class _FakeLLMRequest:
    def __init__(self, headers, content):
        self.headers = headers
        self.content = content


class _FakeAtofExporterConfig:
    def __init__(self):
        self.output_directory = ""
        self.filename = "events.jsonl"
        self.mode = "append"


class _FakeAtofExporter:
    def __init__(self, events, config):
        self.events = events
        self.config = config

    def register(self, name):
        self.events.append(("atof.register", name, self.config.output_directory, self.config.filename))

    def deregister(self, name):
        self.events.append(("atof.deregister", name, self.config.output_directory, self.config.filename))
        return True


class _FakeAtifExporter:
    def __init__(self, events, session_id, agent_name, agent_version, kwargs):
        self.events = events
        self.session_id = session_id
        self.agent_name = agent_name
        self.agent_version = agent_version
        self.kwargs = kwargs

    def register(self, name):
        self.events.append(("atif.register", name, self.session_id))

    def deregister(self, name):
        self.events.append(("atif.deregister", name, self.session_id))
        return True

    def export_json(self):
        self.events.append(("atif.export", self.session_id))
        return json.dumps({"session_id": self.session_id, "agent_name": self.agent_name})


def _fresh_plugin(monkeypatch, fake):
    existing = sys.modules.get("plugins.observability.nemo_relay")
    if existing is not None:
        existing.reset_for_tests()
    relay_shared_metrics._reset_for_tests()
    relay_runtime._reset_for_tests()
    monkeypatch.setattr(relay_runtime, "_load_nemo_relay", lambda: fake)
    monkeypatch.setitem(sys.modules, "nemo_relay", fake)
    sys.modules.pop("plugins.observability.nemo_relay", None)
    plugin = importlib.import_module("plugins.observability.nemo_relay")
    plugin.reset_for_tests()
    return plugin


def _enable_dynamic_plugin(tmp_path, monkeypatch) -> Path:
    plugins_toml = tmp_path / "plugins.toml"
    plugins_toml.write_text(
        f"""
version = 1

[[dynamic_plugins]]
plugin_id = "fixture"
kind = "rust_dynamic"
manifest_ref = "{(tmp_path / "fixture" / "relay-plugin.toml").as_posix()}"

[dynamic_plugins.config]
mode = "test"
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_NEMO_RELAY_PLUGINS_TOML", str(plugins_toml))
    return plugins_toml


def test_manifest_fields():
    data = yaml.safe_load((PLUGIN_DIR / "plugin.yaml").read_text())
    assert data["name"] == "nemo_relay"
    assert set(data["hooks"]) == {
        "on_session_start",
        "on_session_end",
        "on_session_finalize",
        "on_session_reset",
        "pre_llm_call",
        "post_llm_call",
        "pre_approval_request",
        "post_approval_response",
        "subagent_start",
        "subagent_stop",
    }


def test_nemo_relay_plugin_is_discoverable_as_bundled_plugin(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes_test"))

    manager = PluginManager()
    manager.discover_and_load()

    loaded = manager._plugins["observability/nemo_relay"]
    assert loaded.manifest.name == "nemo_relay"
    assert loaded.manifest.source == "bundled"
    assert not loaded.enabled


<<<<<<< HEAD
def test_nemo_relay_plugin_uses_nemo_relay_runtime(monkeypatch):
    fake_relay = _FakeNemoRelay()
    plugin = _fresh_plugin(monkeypatch, fake_relay)

    plugin.on_session_start(session_id="s1")

    assert any(event[0] == "scope.push" for event in fake_relay.events)


def test_nemo_relay_plugin_emits_llm_tool_and_exports_atif(tmp_path, monkeypatch):
    fake = _FakeNemoRelay()
    plugin = _fresh_plugin(monkeypatch, fake)
    monkeypatch.setenv("HERMES_NEMO_RELAY_ATOF_ENABLED", "1")
    monkeypatch.setenv("HERMES_NEMO_RELAY_ATOF_OUTPUT_DIRECTORY", str(tmp_path / "atof"))
    monkeypatch.setenv("HERMES_NEMO_RELAY_ATIF_ENABLED", "1")
    monkeypatch.setenv("HERMES_NEMO_RELAY_ATIF_OUTPUT_DIRECTORY", str(tmp_path / "atif"))

    base = {
        "session_id": "s1",
        "task_id": "t1",
        "turn_id": "turn-1",
        "telemetry_schema_version": "hermes.observer.v1",
    }
    plugin.on_session_start(**base, model="demo-model", platform="cli")
    plugin.on_pre_api_request(
        **base,
        api_request_id="api-1",
        provider="openai",
        model="demo-model",
        request={"method": "POST", "body": {"messages": [{"role": "user", "content": "hi"}]}},
    )
    plugin.on_post_api_request(
        **base,
        api_request_id="api-1",
        response={"assistant_message": {"role": "assistant", "content": "hello"}},
    )
    plugin.on_pre_tool_call(**base, tool_name="read_file", tool_call_id="tool-1", args={"path": "x"})
    plugin.on_post_tool_call(**base, tool_name="read_file", tool_call_id="tool-1", result='{"ok": true}', status="ok")
    plugin.on_session_end(**base, completed=True, interrupted=False)
    plugin.on_session_finalize(**base, reason="shutdown")

    event_names = [event[0] for event in fake.events]
    assert "atof.register" in event_names
    assert "atif.register" in event_names
    assert "llm.call" in event_names
    assert "llm.call_end" in event_names
    assert "tool.call" in event_names
    assert "tool.call_end" in event_names
    assert "scope.pop" in event_names
    assert (tmp_path / "atif" / "hermes-atif-s1.json").exists()


def test_nemo_relay_plugin_closes_api_span_on_error(monkeypatch):
    fake = _FakeNemoRelay()
    plugin = _fresh_plugin(monkeypatch, fake)
    base = {
        "session_id": "s1",
        "task_id": "t1",
        "turn_id": "turn-1",
        "telemetry_schema_version": "hermes.observer.v1",
    }

    plugin.on_pre_api_request(
        **base,
        api_request_id="api-err",
        provider="openai",
        model="demo-model",
        request={"body": {"messages": [{"role": "user", "content": "hi"}]}},
    )
    plugin.on_api_request_error(
        **base,
        api_request_id="api-err",
        error={"type": "RateLimitError", "message": "rate limited"},
        retryable=True,
        reason="rate_limit",
    )

    call_end = next(event for event in fake.events if event[0] == "llm.call_end")
    assert call_end[1] == ("llm", "openai")
    assert call_end[2] == {"error": {"type": "RateLimitError", "message": "rate limited"}}
    assert call_end[3]["data"]["reason"] == "rate_limit"
    assert not plugin._get_runtime().sessions["s1"].llm_spans


def test_nemo_relay_plugin_emits_approval_marks(monkeypatch):
    fake = _FakeNemoRelay()
    plugin = _fresh_plugin(monkeypatch, fake)

    plugin.on_pre_approval_request(session_id="s1", approval_id="approval-1", tool_name="shell")
    plugin.on_post_approval_response(session_id="s1", approval_id="approval-1", approved=True)

    mark_names = [event[1] for event in fake.events if event[0] == "scope.event"]
    assert "hermes.approval.request" in mark_names
    assert "hermes.approval.response" in mark_names


def test_nemo_relay_plugin_emits_unmatched_fallback_marks(monkeypatch):
    fake = _FakeNemoRelay()
    plugin = _fresh_plugin(monkeypatch, fake)

    plugin.on_post_api_request(session_id="s1", api_request_id="missing-api", response={"ok": True})
    plugin.on_api_request_error(
        session_id="s1",
        api_request_id="missing-api",
        error={"type": "TimeoutError", "message": "timed out"},
    )
    plugin.on_post_tool_call(session_id="s1", tool_call_id="missing-tool", result={"ok": True})

    mark_names = [event[1] for event in fake.events if event[0] == "scope.event"]
    assert "hermes.api.response.unmatched" in mark_names
    assert "hermes.api.error" in mark_names
    assert "hermes.tool.response.unmatched" in mark_names


def test_nemo_relay_plugin_metadata_promotes_trajectory_and_subagent_ids(monkeypatch):
    fake = _FakeNemoRelay()
    plugin = _fresh_plugin(monkeypatch, fake)

    plugin.on_pre_llm_call(
        session_id="parent-session",
        task_id="task-1",
        turn_id="turn-1",
        telemetry_schema_version="hermes.observer.v1",
    )
    plugin.on_subagent_start(
        parent_session_id="parent-session",
        parent_turn_id="turn-1",
        parent_subagent_id="parent-sa",
        child_session_id="child-session",
        child_subagent_id="child-sa",
        child_role="leaf",
        telemetry_schema_version="hermes.observer.v1",
    )
    plugin.on_subagent_stop(
        parent_session_id="parent-session",
        parent_turn_id="turn-1",
        child_session_id="child-session",
        child_role="leaf",
        child_status="completed",
        telemetry_schema_version="hermes.observer.v1",
    )

    turn_mark = next(event for event in fake.events if event[0] == "scope.event" and event[1] == "hermes.turn.start")
    turn_metadata = turn_mark[2]["metadata"]
    assert turn_metadata["session_id"] == "parent-session"
    assert turn_metadata["trajectory_id"] == "parent-session"

    start_mark = next(event for event in fake.events if event[0] == "scope.event" and event[1] == "hermes.subagent.start")
    start_metadata = start_mark[2]["metadata"]
    assert start_metadata["parent_session_id"] == "parent-session"
    assert start_metadata["parent_trajectory_id"] == "parent-session"
    assert start_metadata["child_session_id"] == "child-session"
    assert start_metadata["child_trajectory_id"] == "child-session"
    assert start_metadata["child_subagent_id"] == "child-sa"
    assert start_metadata["child_role"] == "leaf"

    stop_mark = next(event for event in fake.events if event[0] == "scope.event" and event[1] == "hermes.subagent.stop")
    assert stop_mark[2]["metadata"]["child_status"] == "completed"


def test_nemo_relay_plugin_reparents_child_session_scope_for_embedded_atif(monkeypatch):
    fake = _FakeNemoRelay()
    plugin = _fresh_plugin(monkeypatch, fake)

    plugin.on_session_start(session_id="parent-session")
    plugin.on_subagent_start(
        parent_session_id="parent-session",
        parent_turn_id="turn-1",
        child_session_id="child-session",
        child_subagent_id="child-sa",
        child_role="leaf",
        telemetry_schema_version="hermes.observer.v1",
    )
    plugin.on_session_start(session_id="child-session")

    child_push = next(
        event
        for event in fake.events
        if event[0] == "scope.push" and event[1] == "hermes-session-child-session"
    )
    child_kwargs = child_push[3]
    assert child_kwargs["handle"] == ("scope", "hermes-session-parent-session")
    assert child_kwargs["metadata"]["session_id"] == "child-session"
    assert child_kwargs["metadata"]["trajectory_id"] == "child-session"
    assert child_kwargs["metadata"]["nemo_relay_scope_role"] == "subagent"
    assert child_kwargs["metadata"]["subagent_id"] == "child-sa"
    assert child_kwargs["metadata"]["parent_session_id"] == "parent-session"


def test_nemo_relay_plugin_skips_embedded_child_atif_file_by_default(tmp_path, monkeypatch):
    fake = _FakeNemoRelay()
    plugin = _fresh_plugin(monkeypatch, fake)
    monkeypatch.setenv("HERMES_NEMO_RELAY_ATIF_ENABLED", "1")
    monkeypatch.setenv("HERMES_NEMO_RELAY_ATIF_OUTPUT_DIRECTORY", str(tmp_path / "atif"))

    plugin.on_session_start(session_id="parent-session")
    plugin.on_subagent_start(
        parent_session_id="parent-session",
        child_session_id="child-session",
        child_subagent_id="child-sa",
    )
    plugin.on_session_start(session_id="child-session")
    plugin.on_session_end(session_id="child-session")
    plugin.on_session_finalize(session_id="child-session")
    plugin.on_session_end(session_id="parent-session")
    plugin.on_session_finalize(session_id="parent-session")

    assert (tmp_path / "atif" / "hermes-atif-parent-session.json").exists()
    assert not (tmp_path / "atif" / "hermes-atif-child-session.json").exists()


def test_nemo_relay_plugin_can_write_embedded_child_atif_file_in_all_mode(tmp_path, monkeypatch):
    fake = _FakeNemoRelay()
    plugin = _fresh_plugin(monkeypatch, fake)
    monkeypatch.setenv("HERMES_NEMO_RELAY_ATIF_ENABLED", "1")
    monkeypatch.setenv("HERMES_NEMO_RELAY_ATIF_OUTPUT_DIRECTORY", str(tmp_path / "atif"))
    monkeypatch.setenv("HERMES_NEMO_RELAY_ATIF_SUBAGENT_EXPORT_MODE", "all")

    plugin.on_session_start(session_id="parent-session")
    plugin.on_subagent_start(
        parent_session_id="parent-session",
        child_session_id="child-session",
        child_subagent_id="child-sa",
    )
    plugin.on_session_start(session_id="child-session")
    plugin.on_session_end(session_id="child-session")
    plugin.on_session_finalize(session_id="child-session")
    plugin.on_session_end(session_id="parent-session")
    plugin.on_session_finalize(session_id="parent-session")

    assert (tmp_path / "atif" / "hermes-atif-parent-session.json").exists()
    assert (tmp_path / "atif" / "hermes-atif-child-session.json").exists()


def test_nemo_relay_plugin_can_initialize_plugins_toml(tmp_path, monkeypatch):
    fake = _FakeNemoRelay()
    plugin = _fresh_plugin(monkeypatch, fake)
    plugins_toml = tmp_path / "plugins.toml"
    atof_dir = tmp_path / "exports" / "events"
    atif_dir = tmp_path / "exports" / "trajectories"
    plugins_toml.write_text(
        f"""
version = 1

[[components]]
kind = "observability"
enabled = true

[components.config.atof]
enabled = true
output_directory = "{atof_dir}"

[components.config.atif]
enabled = true
output_directory = "{atif_dir}"
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_NEMO_RELAY_PLUGINS_TOML", str(plugins_toml))

    plugin.on_session_start(session_id="s1")

    assert any(event[0] == "plugin.initialize" for event in fake.events)
    assert not any(event[0] == "atof.register" for event in fake.events)
    assert atof_dir.is_dir()
    assert atif_dir.is_dir()


def test_nemo_relay_plugin_clears_plugins_toml_on_final_session_finalize_and_reinitializes(tmp_path, monkeypatch):
    fake = _FakeNemoRelay()
    plugin = _fresh_plugin(monkeypatch, fake)
    plugins_toml = tmp_path / "plugins.toml"
    plugins_toml.write_text(
        """
version = 1

[[components]]
kind = "observability"
enabled = true
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_NEMO_RELAY_PLUGINS_TOML", str(plugins_toml))

    plugin.on_session_start(session_id="s1")
    plugin.on_session_finalize(session_id="s1", reason="shutdown")
    plugin.on_session_start(session_id="s2")

    event_names = [event[0] for event in fake.events]
    assert event_names.count("plugin.initialize") == 2
    assert event_names.count("plugin.clear") == 1


def test_nemo_relay_plugin_activates_and_owns_dynamic_plugins(tmp_path, monkeypatch):
    fake = _FakeNemoRelay()
    plugin = _fresh_plugin(monkeypatch, fake)
    _enable_dynamic_plugin(tmp_path, monkeypatch)
    monkeypatch.setenv("HERMES_NEMO_RELAY_ATIF_ENABLED", "1")
    monkeypatch.setenv("HERMES_NEMO_RELAY_ATIF_OUTPUT_DIRECTORY", str(tmp_path / "atif"))

    plugin.on_session_start(session_id="s1")
    runtime = plugin._get_runtime()
    assert runtime is not None
    assert runtime._plugin_activation is not None
    llm_result = plugin.on_llm_execution_middleware(
        session_id="s1",
        provider="openai",
        model="fixture",
        request={"messages": []},
        next_call=lambda request: {"request": request},
    )
    tool_result = plugin.on_tool_execution_middleware(
        session_id="s1",
        tool_name="fixture-tool",
        args={"value": 1},
        next_call=lambda args: {"args": args},
    )
    assert llm_result["request"]["intercepted"] is True
    assert tool_result["args"]["intercepted"] is True
    plugin.on_session_finalize(session_id="s1", reason="shutdown")
    assert runtime._plugin_activation is not None
    assert not any(event[0] == "plugin.activation.close" for event in fake.events)
    plugin.on_session_start(session_id="s2")
    plugin.on_session_finalize(session_id="s2", reason="shutdown")
    assert sum(event[0] == "plugin.activate_dynamic" for event in fake.events) == 1

    activation = next(event for event in fake.events if event[0] == "plugin.activate_dynamic")
    assert "dynamic_plugins" not in activation[1]
    assert activation[2] == [
        {
            "plugin_id": "fixture",
            "kind": "rust_dynamic",
            "manifest_ref": str(tmp_path / "fixture" / "relay-plugin.toml"),
            "config": {"mode": "test"},
        }
    ]
    event_names = [event[0] for event in fake.events]
    assert "plugin.clear" not in event_names
    assert event_names.index("subscribers.flush") < event_names.index("atif.export")
    assert event_names.index("atif.export") < event_names.index("atif.deregister")

    runtime.shutdown()
    event_names = [event[0] for event in fake.events]
    assert event_names.index("atif.deregister") < event_names.index("plugin.activation.close")


def test_nemo_relay_rejects_gateway_dynamic_config_with_actionable_diagnostic(
    tmp_path, monkeypatch, caplog
):
    fake = _FakeNemoRelay()
    plugin = _fresh_plugin(monkeypatch, fake)
    plugins_toml = tmp_path / "plugins.toml"
    plugins_toml.write_text(
        """
version = 1

[[plugins.dynamic]]
manifest = "plugins/fixture/relay-plugin.toml"

[plugins.dynamic.config]
mode = "test"
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_NEMO_RELAY_PLUGINS_TOML", str(plugins_toml))

    with caplog.at_level("ERROR"):
        plugin.on_session_start(session_id="s1")

    assert not any(event[0] == "plugin.activate_dynamic" for event in fake.events)
    initialize = next(event for event in fake.events if event[0] == "plugin.initialize")
    assert initialize[1] == {"version": 1}
    assert "does not expose the CLI lifecycle resolver" in caplog.text
    assert "Use Moor-owned [[dynamic_plugins]]" in caplog.text


def test_nemo_relay_explicit_dynamic_paths_resolve_from_plugins_toml(tmp_path, monkeypatch):
    fake = _FakeNemoRelay()
    plugin = _fresh_plugin(monkeypatch, fake)
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    plugins_toml = config_dir / "plugins.toml"
    plugins_toml.write_text(
        """
version = 1

[[dynamic_plugins]]
plugin_id = "worker-fixture"
kind = "worker"
manifest_ref = "../plugins/worker/relay-plugin.toml"
environment_ref = "../environments/worker-fixture"
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_NEMO_RELAY_PLUGINS_TOML", str(plugins_toml))

    plugin.on_session_start(session_id="s1")

    activation = next(event for event in fake.events if event[0] == "plugin.activate_dynamic")
    assert activation[2] == [
        {
            "plugin_id": "worker-fixture",
            "kind": "worker",
            "manifest_ref": str(tmp_path / "plugins" / "worker" / "relay-plugin.toml"),
            "environment_ref": str(tmp_path / "environments" / "worker-fixture"),
            "config": {},
        }
    ]
    runtime = plugin._get_runtime()
    assert runtime is not None
    runtime.shutdown()


@pytest.mark.parametrize(
    ("provider", "api_mode", "expected_surface", "should_rewrite"),
    [
        ("custom", "chat_completions", "openai.chat_completions", True),
        ("openai-codex", "codex_responses", "openai.responses", True),
        ("anthropic", "anthropic_messages", "anthropic.messages", True),
        ("custom", "anthropic_messages", "anthropic.messages", True),
        ("bedrock", "bedrock_converse", "bedrock", False),
    ],
)
def test_nemo_relay_managed_llm_uses_wire_protocol_for_interceptor_dispatch(
=======
def test_shared_metrics_and_rich_plugin_share_one_core_session(
>>>>>>> upstream/main
    tmp_path,
    monkeypatch,
):
    from agent import relay_llm

    fake = _FakeNemoRelay()
    hermes_home = tmp_path / "hermes-home"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.setenv("HERMES_NEMO_RELAY_ATIF_ENABLED", "1")
    monkeypatch.setenv(
        "HERMES_NEMO_RELAY_ATIF_OUTPUT_DIRECTORY", str(tmp_path / "atif")
    )
    monkeypatch.setattr(
        "hermes_cli.config.read_raw_config_readonly",
        lambda: {"telemetry": {"shared_metrics": {"enabled": True}}},
    )
    plugin = _fresh_plugin(monkeypatch, fake)
    manager = PluginManager()

    class _Context:
        def register_hook(self, name, callback):
            manager._hooks.setdefault(name, []).append(callback)

    plugin.register(_Context())
    monkeypatch.setattr(plugin_api, "_plugin_manager", manager)

    event = {
        "session_id": "s1",
        "task_id": "t1",
        "api_request_id": "api-1",
        "provider": "anthropic",
        "model": "claude-sonnet",
        "platform": "cli",
    }
    coordinator = relay_runtime.SESSION_COORDINATOR
    lease = coordinator.acquire_conversation(
        profile_key=relay_runtime.current_profile_key(),
        session_id="s1",
        platform="cli",
        model=event["model"],
    )
    lifecycle.invoke_hook("on_session_start", **event)
    turn = coordinator.begin_turn(
        lease,
        turn_id="turn-1",
        task_id="t1",
    )
    lifecycle.invoke_hook(
        "pre_api_request",
        **event,
        request={"body": {"messages": [{"role": "user", "content": "hi"}]}},
    )
    relay_llm.execute(
        {"messages": [{"role": "user", "content": "hi"}]},
        lambda _request: {
            "assistant_message": {"role": "assistant", "content": "hello"}
        },
        session_id="s1",
        name="anthropic",
        model_name="claude-sonnet",
        metadata={"api_request_id": "api-1", "api_mode": "custom"},
    )
    lifecycle.invoke_hook(
        "post_api_request",
        **event,
        response={"assistant_message": {"role": "assistant", "content": "hello"}},
    )
    coordinator.end_turn(turn, outcome="success")
    coordinator.release_conversation(lease)
    lifecycle.finalize_session(session_id="s1")

    session_pushes = [
        item
        for item in fake.events
        if item[0] == "scope.push" and item[1] == relay_runtime.SESSION_SCOPE
    ]
    assert len(session_pushes) == 1
    register_metrics = next(
        index
        for index, item in enumerate(fake.events)
        if item[0] == "subscribers.register"
        and item[1].startswith("hermes.nemo_relay.shared_metrics.")
    )
    register_atif = next(
        index for index, item in enumerate(fake.events) if item[0] == "atif.register"
    )
    open_session = fake.events.index(session_pushes[0])
    assert register_metrics < register_atif < open_session

    plugin_runtime = plugin._get_runtime()
    assert plugin_runtime is not None
    assert not plugin_runtime.sessions
    assert relay_runtime.get_session_handle("s1") is None
    packages = list(
        (hermes_home / "telemetry" / "shared_metrics" / "outbox").glob("*.json")
    )
    assert len(packages) == 1
    package = json.loads(packages[0].read_text(encoding="utf-8"))
    assert package["metrics"][0]["name"] == "hermes.model_route.count"
    assert package["metrics"][0]["value"] == 1
    assert (tmp_path / "atif" / "hermes-atif-s1.json").exists()


def test_real_binding_shares_plugin_configuration_across_two_profiles(
    tmp_path,
    monkeypatch,
):
    relay = pytest.importorskip("nemo_relay")
    if getattr(relay, "_native", None) is None:
        pytest.skip("NeMo Relay native binding is unavailable on this platform")
    plugin = _fresh_plugin(monkeypatch, relay)
    original_initialize = relay.plugin.initialize
    original_clear = relay.plugin.clear
    original_clear()
    initialize_calls = []
    clear_calls = 0

    async def _initialize(config):
        initialize_calls.append(config)
        return await original_initialize(config)

    def _clear():
        nonlocal clear_calls
        clear_calls += 1
        return original_clear()

    monkeypatch.setattr(relay.plugin, "initialize", _initialize)
    monkeypatch.setattr(relay.plugin, "clear", _clear)
    monkeypatch.setattr(
        plugin,
        "_load_settings",
        lambda: plugin._Settings(plugins_config={"version": 1}),
    )
    profile_a = str(tmp_path / "profile-a")
    profile_b = str(tmp_path / "profile-b")
    host_a = relay_runtime.RelayRuntime(relay=relay, profile_key=profile_a)
    host_b = relay_runtime.RelayRuntime(relay=relay, profile_key=profile_b)

    try:
        runtime_a = plugin._get_runtime(profile_key=profile_a, host=host_a)
        runtime_b = plugin._get_runtime(profile_key=profile_b, host=host_b)
        assert runtime_a is not None
        assert runtime_b is not None
        runtime_a.ensure_session({"session_id": "session-a"})
        runtime_b.ensure_session({"session_id": "session-b"})

        assert initialize_calls == [{"version": 1}]
        assert relay.plugin.report() is not None

        runtime_a.close_session({"session_id": "session-a"})

        assert clear_calls == 0
        assert relay.plugin.report() is not None
        assert runtime_b.host.get_session("session-b") is not None

        runtime_b.close_session({"session_id": "session-b"})

        assert clear_calls == 1
        assert relay.plugin.report() is None
    finally:
        plugin.reset_for_tests()
        host_a.shutdown()
        host_b.shutdown()
        original_clear()


def test_relay_tool_request_rewrite_precedes_hermes_authorization_boundary(
    tmp_path,
    monkeypatch,
):
    from hermes_cli.middleware import apply_tool_request_middleware

    fake = _FakeNemoRelay()
    plugin = _fresh_plugin(monkeypatch, fake)
    _enable_dynamic_plugin(tmp_path, monkeypatch)
    plugin.on_session_start(session_id="s1")

    result = apply_tool_request_middleware(
        "fixture-tool",
        {"value": 1},
        session_id="s1",
        tool_call_id="tool-1",
    )

    assert result.payload == {"intercepted": True, "value": 1}
    assert result.trace[0] == {"source": "nemo_relay"}


