"""nemo_relay — optional Moor plugin for NeMo Relay observability."""

from __future__ import annotations

import atexit
import asyncio
import inspect
import json
import logging
import os
import threading
import tomllib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from agent import relay_runtime

logger = logging.getLogger(__name__)

_INIT_FAILED = object()
_LOCK = threading.RLock()
_RUNTIMES: dict[str, "_Runtime | object"] = {}
_SESSION_INITIALIZER_NAME = "hermes.nemo_relay.rich_observability"


@dataclass
class _SessionState:
    session_id: str
    relay_session: relay_runtime.RelaySession | None = None
    handle: Any = None
    atif_exporter: Any = None
    atif_subscriber_name: str = ""
    is_embedded_subagent: bool = False
    parent_session_id: str = ""
    # Flipped when a Relay scope operation for this session raises — an
    # errored session's exporter state is unreliable and its export can be
    # pathologically slow, so close_session skips the ATIF export for it.
    scope_errored: bool = False


@dataclass
class _SubagentContext:
    parent_session_id: str
    metadata: dict[str, Any]


@dataclass
class _Settings:
    plugins_toml_path: str = ""
    plugins_config: dict[str, Any] | None = None
    dynamic_plugins: list[dict[str, Any]] = field(default_factory=list)
    atof_enabled: bool = False
    atof_output_directory: str = ""
    atof_filename: str = "hermes-atof.jsonl"
    atof_mode: str = "append"
    atif_enabled: bool = False
    atif_output_directory: str = ""
    atif_filename_template: str = "hermes-atif-{session_id}.json"
    atif_subagent_export_mode: str = "embedded"
    atif_agent_name: str = "Moor Agent"
    atif_agent_version: str = "unknown"
    atif_model_name: str = "unknown"
    # Wall-clock budget for one session's ATIF export (serialize + write).
    # A multi-day session's trace can take minutes to serialize; when the
    # export runs inside a session-finalize hook that budget is somebody
    # else's shutdown window. <= 0 disables the bound.
    atif_export_timeout_s: float = 30.0


class _ProcessPluginConfiguration:
    """Own Relay's process-global plugin configuration across profile runtimes."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._key: str | None = None
        self._plugin_mod: Any = None
        self._activation: Any = None
        self._owners: set[int] = set()

    def acquire(
        self,
        owner: "_Runtime",
        plugin_mod: Any,
        plugin_config: dict[str, Any],
        dynamic_plugins: list[dict[str, Any]],
    ) -> tuple[bool, Any]:
        owner_id = id(owner)
        key = _plugin_configuration_key(plugin_config, dynamic_plugins)
        with self._lock:
            if owner_id in self._owners:
                return True, self._activation
            if self._owners:
                if self._plugin_mod is plugin_mod and self._key == key:
                    self._owners.add(owner_id)
                    return True, self._activation
                logger.warning(
                    "NeMo Relay plugin configuration is already active for another "
                    "Hermes profile; keeping the existing process-global configuration "
                    "and using direct observability for this profile."
                )
                return False, None

            activation = None
            if dynamic_plugins:
                initialize_dynamic = getattr(
                    plugin_mod,
                    "initialize_with_dynamic_plugins",
                    None,
                )
                if callable(initialize_dynamic):
                    try:
                        activation = _resolve_awaitable(
                            initialize_dynamic(plugin_config, dynamic_plugins)
                        )
                    except Exception as exc:
                        logger.warning(
                            "NeMo Relay dynamic plugin activation failed; continuing "
                            "with static observability only: %s",
                            exc,
                        )
                else:
                    logger.warning(
                        "NeMo Relay dynamic plugins require a binding that exposes "
                        "plugin.initialize_with_dynamic_plugins (available in NeMo "
                        "Relay 0.6+). Continuing with static observability only."
                    )

            if activation is None:
                initialize = getattr(plugin_mod, "initialize", None)
                if not callable(initialize):
                    return False, None
                try:
                    _resolve_awaitable(initialize(plugin_config))
                except Exception as exc:
                    logger.debug(
                        "NeMo Relay plugins.toml init failed: %s",
                        exc,
                        exc_info=True,
                    )
                    return False, None

            self._key = key
            self._plugin_mod = plugin_mod
            self._activation = activation
            self._owners.add(owner_id)
            return True, activation

    def release(self, owner: "_Runtime", nemo_relay: Any) -> None:
        owner_id = id(owner)
        with self._lock:
            if owner_id not in self._owners:
                return
            self._owners.remove(owner_id)
            if self._owners:
                return

            failures: list[str] = []
            activation = self._activation
            plugin_mod = self._plugin_mod
            try:
                if activation is not None:
                    try:
                        _flush_relay_subscribers(nemo_relay)
                    except Exception as exc:
                        failures.append(f"subscriber flush failed: {exc}")
                    close = getattr(activation, "close", None)
                    if callable(close):
                        try:
                            _resolve_awaitable(close())
                        except Exception as exc:
                            failures.append(
                                f"dynamic plugin activation close failed: {exc}"
                            )
                    else:
                        failures.append("dynamic plugin activation has no close method")
                else:
                    clear = getattr(plugin_mod, "clear", None)
                    if callable(clear):
                        try:
                            _resolve_awaitable(clear())
                        except Exception as exc:
                            failures.append(
                                f"static plugin configuration clear failed: {exc}"
                            )
            finally:
                self._key = None
                self._plugin_mod = None
                self._activation = None

            if failures:
                raise RuntimeError("; ".join(failures))

    def reset_for_tests(self) -> None:
        with self._lock:
            self._key = None
            self._plugin_mod = None
            self._activation = None
            self._owners.clear()


_PLUGIN_CONFIGURATION = _ProcessPluginConfiguration()


class _Runtime:
    def __init__(
        self,
        nemo_relay: Any,
        settings: _Settings,
        host: relay_runtime.RelayRuntime,
    ) -> None:
        self.nemo_relay = nemo_relay
        self.settings = settings
        self.host = host
        self._sessions_lock = threading.RLock()
        self.sessions: dict[str, _SessionState] = {}
        self.subagent_contexts: dict[str, _SubagentContext] = {}
        self.atof_exporter: Any = None
        self._atof_subscriber_name = f"hermes.nemo_relay.atof.{self.host.runtime_id}"
        self._execution_consumer_name = (
            f"hermes.nemo_relay.rich_observability.{self.host.runtime_id}"
        )
        self._execution_consumer_retained = False
        self._plugin_activation: Any = None
        self._shutdown_registered = False
        self._plugin_config_initialized = self._configure_plugins_toml()
        self._plugin_config_needs_reinit = False
        if not self._plugin_config_initialized:
            self._activate_direct_fallbacks()
        self._sync_managed_execution()

    def _sync_managed_execution(self) -> None:
        required = bool(
            self._plugin_config_initialized
            or self.atof_exporter is not None
            or self.settings.atif_enabled
        )
        if required and not self._execution_consumer_retained:
            self.host.retain_managed_execution(self._execution_consumer_name)
            self._execution_consumer_retained = True
        elif not required and self._execution_consumer_retained:
            self.host.release_managed_execution(self._execution_consumer_name)
            self._execution_consumer_retained = False

    def _configure_plugins_toml(self) -> bool:
        if not self.settings.plugins_config:
            return False
        plugin_mod = getattr(self.nemo_relay, "plugin", None)
        if plugin_mod is None:
            return False
        plugin_config = _static_plugin_config(self.settings.plugins_config)
        self._ensure_plugin_config_output_dirs(plugin_config)
        initialized, activation = _PLUGIN_CONFIGURATION.acquire(
            self,
            plugin_mod,
            plugin_config,
            self.settings.dynamic_plugins,
        )
        self._plugin_activation = activation
        if activation is not None:
            self._ensure_shutdown_registered()
        return initialized

    def _ensure_shutdown_registered(self) -> None:
        if self._shutdown_registered:
            return
        atexit.register(self.shutdown)
        self._shutdown_registered = True

    def _clear_plugins_toml(self) -> None:
        if not self._plugin_config_initialized:
            return
        try:
            _PLUGIN_CONFIGURATION.release(self, self.nemo_relay)
        finally:
            self._plugin_activation = None
            self._plugin_config_initialized = False
            self._plugin_config_needs_reinit = bool(self.settings.plugins_config)

    def _activate_direct_fallbacks(self) -> None:
        self._plugin_config_needs_reinit = False
        self._configure_atof()

    def _maybe_reinitialize_plugins_toml(self) -> None:
        if not self._plugin_config_needs_reinit or self._plugin_config_initialized:
            return
        self._plugin_config_initialized = self._configure_plugins_toml()
        if not self._plugin_config_initialized:
            self._activate_direct_fallbacks()
            self._sync_managed_execution()
            return
        self._clear_atof()
        self._plugin_config_needs_reinit = False
        self._sync_managed_execution()

    def _plugins_toml_owns_exporter(self, exporter_name: str) -> bool:
        return self._plugin_config_initialized and _observability_exporter_enabled(
            self.settings.plugins_config,
            exporter_name,
        )

    def _ensure_plugin_config_output_dirs(self, config: dict[str, Any]) -> None:
        for component in config.get("components", []):
            if not isinstance(component, dict):
                continue
            if component.get("kind") != "observability":
                continue
            if component.get("enabled") is False:
                continue
            component_config = component.get("config")
            if not isinstance(component_config, dict):
                continue
            for exporter_name in ("atof", "atif"):
                exporter_config = component_config.get(exporter_name)
                if not isinstance(exporter_config, dict):
                    continue
                output_directory = exporter_config.get("output_directory")
                if isinstance(output_directory, str) and output_directory.strip():
                    Path(output_directory).mkdir(parents=True, exist_ok=True)

    def _configure_atof(self) -> None:
        if not self.settings.atof_enabled or self.atof_exporter is not None:
            return
        config = self.nemo_relay.AtofExporterConfig()
        if self.settings.atof_output_directory:
            Path(self.settings.atof_output_directory).mkdir(parents=True, exist_ok=True)
            config.output_directory = self.settings.atof_output_directory
        config.filename = self.settings.atof_filename
        if self.settings.atof_mode.lower() == "overwrite":
            config.mode = self.nemo_relay.AtofExporterMode.Overwrite
        else:
            config.mode = self.nemo_relay.AtofExporterMode.Append
        self.atof_exporter = self.nemo_relay.AtofExporter(config)
        self.atof_exporter.register(self._atof_subscriber_name)

    def _clear_atof(self) -> None:
        if self.atof_exporter is None:
            return
        deregister = getattr(self.atof_exporter, "deregister", None)
        if callable(deregister):
            try:
                deregister(self._atof_subscriber_name)
            except Exception:
                logger.debug("NeMo Relay ATOF deregister failed", exc_info=True)
        self.atof_exporter = None
        self._sync_managed_execution()

    def prepare_session(self, kwargs: dict[str, Any]) -> _SessionState:
        """Register per-session subscribers without opening the core scope."""
        session_id = _session_id(kwargs)
        with self._sessions_lock:
            self._maybe_reinitialize_plugins_toml()
            state = self.sessions.get(session_id)
            if state is not None:
                return state

            state = _SessionState(session_id=session_id)
            if self.settings.atif_enabled and not self._plugins_toml_owns_exporter("atif"):
                state.atif_exporter = self.nemo_relay.AtifExporter(
                    session_id,
                    self.settings.atif_agent_name,
                    self.settings.atif_agent_version,
                    model_name=str(kwargs.get("model") or self.settings.atif_model_name),
                    extra={
                        "source": "hermes-agent",
                        "plugin": "observability/nemo_relay",
                    },
                )
                state.atif_subscriber_name = (
                    f"hermes.nemo_relay.atif.{self.host.runtime_id}.{session_id}"
                )
                state.atif_exporter.register(state.atif_subscriber_name)
            self.sessions[session_id] = state
            return state

    def ensure_session(self, kwargs: dict[str, Any]) -> _SessionState:
        state = self.prepare_session(kwargs)
        if state.relay_session is not None:
            return state

        rich_metadata = _metadata(kwargs)
        with self._sessions_lock:
            subagent_context = self.subagent_contexts.get(state.session_id)
        if subagent_context is not None:
            rich_metadata = {**rich_metadata, **subagent_context.metadata}
        relay_session = self.host.ensure_session(
            kwargs,
            data={"session_id": state.session_id},
            metadata=rich_metadata,
        )
        if relay_session is None:
            raise RuntimeError("Hermes core Relay session is unavailable")
        state.relay_session = relay_session
        state.handle = relay_session.handle
        if subagent_context is not None:
            state.is_embedded_subagent = True
            state.parent_session_id = subagent_context.parent_session_id
        return state

    def run_in_session(
        self,
        state: _SessionState,
        callback: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        if state.relay_session is None:
            raise RuntimeError("Hermes core Relay session is unavailable")
        try:
            return self.host.run_in_session(
                state.relay_session,
                callback,
                *args,
                # Bounded: this wrapper serves every mark/event the plugin
                # emits (turn start/end, approvals, subagent marks), and it
                # runs synchronously on the agent's conversation thread. The
                # host default (timeout=None) is an UNBOUNDED native call —
                # a wedged native Relay pipeline then blocks the agent
                # between API calls with zero activity ticks until the cron
                # 600s inactivity kill / gateway idle timeout fires (the
                # core's scope push/pop/flush sites were bounded for the
                # same reason after the 2026-08-10 delegation stall; these
                # plugin marks were the missed sibling class). On breach we
                # lose one telemetry span, never the agent.
                timeout=relay_runtime._SCOPE_OP_TIMEOUT,
                **kwargs,
            )
        except TimeoutError:
            # A wedged native pipeline is a session-level condition, not a
            # one-off: flag it so close_session skips the (potentially very
            # slow) ATIF export, and warn ONCE so the sick pipeline is
            # visible before it costs anything bigger.
            if not state.scope_errored:
                logger.warning(
                    "Relay scope operation for session %s exceeded %.0fs; "
                    "native pipeline appears wedged — further exports for "
                    "this session will be skipped",
                    state.session_id,
                    relay_runtime._SCOPE_OP_TIMEOUT,
                )
            state.scope_errored = True
            raise
        except Exception:
            # A failed scope operation leaves the session's Relay/exporter
            # state unreliable; remember it so close_session can skip the
            # (potentially very slow) ATIF export for this session.
            state.scope_errored = True
            raise

    def export_atif(self, state: _SessionState) -> None:
        if not self.settings.atif_enabled or state.atif_exporter is None:
            return
        if state.is_embedded_subagent and self.settings.atif_subagent_export_mode != "all":
            return
        if state.scope_errored:
            logger.warning(
                "Skipping ATIF export for session %s: a prior Relay scope "
                "operation failed, exporter state is unreliable",
                state.session_id,
            )
            return
        output_dir = self.settings.atif_output_directory
        if not output_dir:
            return
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        filename = self.settings.atif_filename_template.format(session_id=state.session_id)

        def _export() -> None:
            Path(output_dir, filename).write_text(
                state.atif_exporter.export_json(), encoding="utf-8"
            )

        timeout = self.settings.atif_export_timeout_s
        if timeout is None or timeout <= 0:
            _export()
            return

        # Bounded: export_json() on a long session can take minutes, and
        # close_session runs inside session-finalize/shutdown paths where
        # that time is somebody else's stop window. On timeout the worker
        # thread finishes (or leaks) on its own; the partial file, if any,
        # is overwritten by the next successful export.
        error: dict[str, BaseException] = {}

        def _runner() -> None:
            try:
                _export()
            except BaseException as exc:  # re-raised below when it beat the clock
                error["exc"] = exc

        thread = threading.Thread(
            target=_runner,
            name=f"hermes-nemo-relay-atif-export-{state.session_id}",
            daemon=True,
        )
        thread.start()
        thread.join(timeout=timeout)
        if thread.is_alive():
            raise TimeoutError(
                f"ATIF export for session {state.session_id} exceeded "
                f"{timeout:.0f}s; abandoning the wait (export thread left "
                "to finish on its own)"
            )
        if "exc" in error:
            raise error["exc"]

    def close_session(
        self,
        kwargs: dict[str, Any],
        *,
        close_host: bool = True,
    ) -> None:
        session_id = _session_id(kwargs)
        with self._sessions_lock:
            self.subagent_contexts.pop(session_id, None)
            state = self.sessions.pop(session_id, None)
        if state is None:
            return
        failures: list[str] = []
        if close_host:
            try:
                self.host.close_session(kwargs)
            except Exception as exc:
                failures.append(f"core session close failed: {exc}")
        try:
            self.export_atif(state)
        except Exception as exc:
            failures.append(f"ATIF export failed: {exc}")
        if state.atif_exporter is not None and state.atif_subscriber_name:
            try:
                state.atif_exporter.deregister(state.atif_subscriber_name)
            except Exception as exc:
                failures.append(f"ATIF deregister failed: {exc}")
        with self._sessions_lock:
            if (
                self._plugin_config_initialized
                and self._plugin_activation is None
                and not self.sessions
            ):
                try:
                    self._clear_plugins_toml()
                except Exception as exc:
                    failures.append(f"plugin configuration clear failed: {exc}")
            elif (
                self.settings.plugins_config
                and self._plugin_activation is None
                and not self.sessions
            ):
                self._plugin_config_needs_reinit = True
        if failures:
            logger.warning(
                "NeMo Relay session %s teardown completed with errors: %s",
                session_id,
                "; ".join(failures),
            )

    def shutdown(self) -> None:
        """Close active sessions and the process-lifetime plugin activation."""
        failures: list[str] = []
        with self._sessions_lock:
            session_ids = list(self.sessions)
        for session_id in session_ids:
            try:
                self.close_session({"session_id": session_id, "reason": "runtime_shutdown"})
            except Exception as exc:
                failures.append(f"session {session_id} close failed: {exc}")
        if self._plugin_config_initialized:
            try:
                self._clear_plugins_toml()
            except Exception as exc:
                failures.append(f"plugin runtime close failed: {exc}")
        self._clear_atof()
        if self._execution_consumer_retained:
            self.host.release_managed_execution(self._execution_consumer_name)
            self._execution_consumer_retained = False
        if self._shutdown_registered and self._plugin_activation is None:
            atexit.unregister(self.shutdown)
            self._shutdown_registered = False
        if failures:
            logger.warning(
                "NeMo Relay runtime shutdown completed with errors: %s",
                "; ".join(failures),
            )

    def mark(self, name: str, kwargs: dict[str, Any]) -> None:
        state = self.ensure_session(kwargs)
        # Prefer the live turn scope over the session scope. Scope events
        # export when their OWNING scope closes: turn scopes close every
        # turn, session scopes only at session end. Parenting marks to the
        # session means a long-lived conversation emits nothing for hours
        # (and nothing at all if the process dies first), so approval and
        # turn marks were invisible on audit dashboards until the operator
        # happened to end the session. Turn scopes give per-turn export
        # with the same parentage semantics — the turn is a child of the
        # session, so the session tree is unchanged.
        handle = state.handle
        turn = relay_runtime.active_turn(state.session_id)
        if turn is not None and turn.handle is not None:
            handle = turn.handle
        self.run_in_session(
            state,
            self.nemo_relay.scope.event,
            name,
            handle=handle,
            data=_jsonable(kwargs),
            metadata=_metadata(kwargs),
        )

    def mark_subagent_start(self, kwargs: dict[str, Any]) -> None:
        parent_state = self.ensure_session(kwargs)
        metadata = _metadata(kwargs)
        child_session_id = _child_session_id(kwargs)
        if child_session_id:
            with self._sessions_lock:
                self.subagent_contexts[child_session_id] = _SubagentContext(
                    parent_session_id=parent_state.session_id,
                    metadata=_subagent_child_metadata(kwargs, metadata),
                )
        self.run_in_session(
            parent_state,
            self.nemo_relay.scope.event,
            "hermes.subagent.start",
            handle=parent_state.handle,
            data=_jsonable(kwargs),
            metadata=metadata,
        )

    def mark_subagent_stop(self, kwargs: dict[str, Any]) -> None:
        child_session_id = _child_session_id(kwargs)
        if child_session_id:
            self.close_session(
                {"session_id": child_session_id},
                close_host=False,
            )
            with self._sessions_lock:
                self.subagent_contexts.pop(child_session_id, None)
        self.mark("hermes.subagent.stop", kwargs)

<<<<<<< HEAD
    def managed_llm_enabled(self) -> bool:
        return (
            (self.settings.adaptive_enabled or self._plugin_activation is not None)
            and callable(getattr(getattr(self.nemo_relay, "llm", None), "execute", None))
            and callable(getattr(self.nemo_relay, "LLMRequest", None))
        )

    def managed_tool_enabled(self) -> bool:
        return (
            (self.settings.adaptive_enabled or self._plugin_activation is not None)
            and callable(getattr(getattr(self.nemo_relay, "tools", None), "execute", None))
        )

    def _run_managed_with_downstream_preservation(
        self,
        next_call: Callable[[Any], Any],
        normalize_payload: Callable[[Any], Any],
        shape_response: Callable[[Any], Any],
        make_managed_execute: Callable[[Callable[[Any], Any]], Any],
        *,
        preserve_raw_response: bool,
    ) -> Any:
        # NeMo Relay's native managed execution may wrap a failing callback as an
        # internal runtime error, hiding the real downstream provider/tool
        # exception. Capture the original here and re-raise it after managed
        # execution so Moor retry classification still sees it. The LLM and tool
        # paths share this scaffolding; they differ only in payload normalization,
        # response shaping, and the Relay call itself.
        raw_response: dict[str, Any] = {"set": False, "value": None, "normalized": None}
        callback_error: Exception | None = None
        downstream_error: BaseException | None = None

        def _impl(next_payload: Any) -> Any:
            nonlocal callback_error, downstream_error
            try:
                raw = next_call(normalize_payload(next_payload))
            except Exception as exc:
                callback_error = exc
                downstream_error = _original_downstream_error(exc)
                raise
            raw_response["set"] = True
            raw_response["value"] = raw
            raw_response["normalized"] = shape_response(raw)
            return raw_response["normalized"]

        try:
            managed_result = _resolve_awaitable(make_managed_execute(_impl))
        except Exception as exc:
            if downstream_error is not None and _is_relay_wrapped_callback_error(exc, callback_error):
                raise downstream_error
            raise
        if (
            preserve_raw_response
            and raw_response["set"]
            and _json_semantically_equal(managed_result, raw_response["normalized"])
        ):
            return raw_response["value"]
        return managed_result

    def execute_llm(self, kwargs: dict[str, Any]) -> Any:
        state = self.ensure_session(kwargs)
        request_body = _jsonable(kwargs.get("request") or {})
        request = self.nemo_relay.LLMRequest({}, request_body)
        next_call = kwargs.get("next_call")
        if not callable(next_call):
            return request_body

        def _normalize(next_request: Any) -> Any:
            next_body = getattr(next_request, "content", next_request)
            return next_body if isinstance(next_body, dict) else request_body

        def _make_managed(impl: Callable[[Any], Any]) -> Any:
            async def _managed_execute() -> Any:
                result = self.nemo_relay.llm.execute(
                    _relay_llm_surface(kwargs),
                    request,
                    impl,
                    handle=state.handle,
                    data=_jsonable(
                        {
                            "turn_id": kwargs.get("turn_id"),
                            "api_request_id": kwargs.get("api_request_id"),
                            "api_call_count": kwargs.get("api_call_count"),
                            "mode": self.settings.adaptive_mode,
                        }
                    ),
                    metadata=_metadata(kwargs),
                    model_name=str(kwargs.get("model") or ""),
                )
                if inspect.isawaitable(result):
                    return await result
                return result

            return _managed_execute()

        return self._run_managed_with_downstream_preservation(
            next_call, _normalize, _llm_response_payload, _make_managed, preserve_raw_response=True
        )

    def execute_tool(self, kwargs: dict[str, Any]) -> Any:
        state = self.ensure_session(kwargs)
        tool_name = str(kwargs.get("tool_name") or "tool")
        args = _jsonable(kwargs.get("args") or {})
        next_call = kwargs.get("next_call")
        if not callable(next_call):
            return args

        def _normalize(next_args: Any) -> Any:
            return next_args if isinstance(next_args, dict) else args

        def _make_managed(impl: Callable[[Any], Any]) -> Any:
            async def _managed_execute() -> Any:
                result = self.nemo_relay.tools.execute(
                    tool_name,
                    args,
                    impl,
                    handle=state.handle,
                    data=_jsonable(
                        {
                            "turn_id": kwargs.get("turn_id"),
                            "api_request_id": kwargs.get("api_request_id"),
                            "tool_call_id": kwargs.get("tool_call_id"),
                            "mode": self.settings.adaptive_mode,
                        }
                    ),
                    metadata=_metadata(kwargs),
                )
                if inspect.isawaitable(result):
                    return await result
                return result

            return _managed_execute()

        return self._run_managed_with_downstream_preservation(
            next_call, _normalize, _jsonable, _make_managed, preserve_raw_response=False
        )


def register(ctx) -> None:
    # Activate dynamic plugins before Moor installs the managed execution
=======
def register(ctx) -> None:
    relay_runtime.SESSION_COORDINATOR.register_session_initializer(
        _SESSION_INITIALIZER_NAME,
        _prepare_core_session,
    )
    # Activate dynamic plugins before Hermes installs the managed execution
>>>>>>> upstream/main
    # boundaries that invoke their interceptors.
    if _load_settings().dynamic_plugins:
        _get_runtime()
    ctx.register_hook("on_session_start", on_session_start)
    ctx.register_hook("on_session_end", on_session_end)
    ctx.register_hook("on_session_finalize", on_session_finalize)
    ctx.register_hook("on_session_reset", on_session_reset)
    ctx.register_hook("pre_llm_call", on_pre_llm_call)
    ctx.register_hook("post_llm_call", on_post_llm_call)
    ctx.register_hook("pre_approval_request", on_pre_approval_request)
    ctx.register_hook("post_approval_response", on_post_approval_response)
    ctx.register_hook("subagent_start", on_subagent_start)
    ctx.register_hook("subagent_stop", on_subagent_stop)


def on_session_start(**kwargs: Any) -> None:
    runtime = _get_runtime()
    if runtime is not None:
        _safe(lambda: runtime.ensure_session(kwargs))


def on_session_end(**kwargs: Any) -> None:
    runtime = _get_runtime()
    if runtime is not None:
        _safe(lambda: (runtime.mark("hermes.session.end", kwargs), runtime.export_atif(runtime.ensure_session(kwargs))))


def on_session_finalize(**kwargs: Any) -> None:
    runtime = _get_runtime()
    if runtime is not None:
        _safe(lambda: runtime.close_session(kwargs, close_host=False))


def on_session_reset(**kwargs: Any) -> None:
    runtime = _get_runtime()
    if runtime is not None:
        _safe(lambda: runtime.close_session(kwargs, close_host=False))


def on_pre_llm_call(**kwargs: Any) -> None:
    runtime = _get_runtime()
    if runtime is not None:
        _safe(lambda: runtime.mark("hermes.turn.start", kwargs))


def on_post_llm_call(**kwargs: Any) -> None:
    runtime = _get_runtime()
    if runtime is not None:
        _safe(lambda: runtime.mark("hermes.turn.end", kwargs))


def on_pre_approval_request(**kwargs: Any) -> None:
    runtime = _get_runtime()
    if runtime is not None:
        _safe(lambda: runtime.mark("hermes.approval.request", kwargs))


def on_post_approval_response(**kwargs: Any) -> None:
    runtime = _get_runtime()
    if runtime is not None:
        _safe(lambda: runtime.mark("hermes.approval.response", kwargs))


def on_subagent_start(**kwargs: Any) -> None:
    runtime = _get_runtime()
    if runtime is not None:
        _safe(lambda: runtime.mark_subagent_start(kwargs))


def on_subagent_stop(**kwargs: Any) -> None:
    runtime = _get_runtime()
    if runtime is not None:
        _safe(lambda: runtime.mark_subagent_stop(kwargs))


def _prepare_core_session(
    host: relay_runtime.RelayRuntime,
    context: dict[str, Any],
) -> None:
    """Register rich subscribers before core creates the conversation scope."""
    runtime = _get_runtime(
        profile_key=str(context.get("profile_key") or host.profile_key),
        host=host,
    )
    if runtime is not None:
        runtime.prepare_session(context)


def _get_runtime(
    *,
    profile_key: str | None = None,
    host: relay_runtime.RelayRuntime | None = None,
) -> Optional[_Runtime]:
    profile_key = profile_key or relay_runtime.current_profile_key()
    with _LOCK:
        runtime = _RUNTIMES.get(profile_key)
        if runtime is _INIT_FAILED:
            return None
        if isinstance(runtime, _Runtime):
            if host is None or runtime.host is host:
                return runtime
            runtime.shutdown()
            _RUNTIMES.pop(profile_key, None)
        try:
            resolved_host = host or relay_runtime.get_runtime(profile_key=profile_key)
            if resolved_host is None:
                raise RuntimeError("Hermes core Relay runtime is unavailable")
            runtime = _Runtime(
                nemo_relay=resolved_host.relay,
                settings=_load_settings(),
                host=resolved_host,
            )
        except Exception as exc:
            logger.debug("NeMo Relay plugin disabled: init failed: %s", exc, exc_info=True)
            _RUNTIMES[profile_key] = _INIT_FAILED
            return None
        _RUNTIMES[profile_key] = runtime
        return runtime


def _load_settings() -> _Settings:
    plugins_toml_path = _env("HERMES_NEMO_RELAY_PLUGINS_TOML")
    plugins_config = _load_plugins_config(plugins_toml_path)
    return _Settings(
        plugins_toml_path=plugins_toml_path,
        plugins_config=plugins_config,
        dynamic_plugins=_dynamic_plugin_specs(plugins_config, plugins_toml_path),
        atof_enabled=_env_bool("HERMES_NEMO_RELAY_ATOF_ENABLED"),
        atof_output_directory=_env("HERMES_NEMO_RELAY_ATOF_OUTPUT_DIRECTORY"),
        atof_filename=_env("HERMES_NEMO_RELAY_ATOF_FILENAME") or "hermes-atof.jsonl",
        atof_mode=_env("HERMES_NEMO_RELAY_ATOF_MODE") or "append",
        atif_enabled=_env_bool("HERMES_NEMO_RELAY_ATIF_ENABLED"),
        atif_output_directory=_env("HERMES_NEMO_RELAY_ATIF_OUTPUT_DIRECTORY"),
        atif_filename_template=_env("HERMES_NEMO_RELAY_ATIF_FILENAME_TEMPLATE") or "hermes-atif-{session_id}.json",
        atif_subagent_export_mode=_atif_subagent_export_mode(),
        atif_agent_name=_env("HERMES_NEMO_RELAY_ATIF_AGENT_NAME") or "Moor Agent",
        atif_agent_version=_env("HERMES_NEMO_RELAY_ATIF_AGENT_VERSION") or "unknown",
        atif_model_name=_env("HERMES_NEMO_RELAY_ATIF_MODEL_NAME") or "unknown",
        atif_export_timeout_s=_env_float(
            "HERMES_NEMO_RELAY_ATIF_EXPORT_TIMEOUT_S", 30.0
        ),
    )


def _static_plugin_config(plugins_config: dict[str, Any]) -> dict[str, Any]:
    """Return Relay's base config without embedding- or gateway-host fields."""
    return {
        key: value
        for key, value in plugins_config.items()
        if key not in {"dynamic_plugins", "plugins"}
    }


def _plugin_configuration_key(
    plugin_config: dict[str, Any],
    dynamic_plugins: list[dict[str, Any]],
) -> str:
    return json.dumps(
        {"config": plugin_config, "dynamic_plugins": dynamic_plugins},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _dynamic_plugin_specs(
    plugins_config: dict[str, Any] | None,
    plugins_toml_path: str = "",
) -> list[dict[str, Any]]:
    if not isinstance(plugins_config, dict):
        return []

    raw_specs = plugins_config.get("dynamic_plugins")
    plugins_section = plugins_config.get("plugins")
    if plugins_section is not None:
        if not isinstance(plugins_section, dict):
            logger.error(
                "Invalid NeMo Relay plugins config: expected [plugins] to be an object; "
                "no dynamic plugins will be activated. Continuing with static "
                "observability only."
            )
            return []
        if plugins_section:
            logger.error(
                "Moor cannot activate Relay gateway [[plugins.dynamic]] records because "
                "the Python binding does not expose the CLI lifecycle resolver for "
                "enablement, trust policy, and worker environments. Use Moor-owned "
                "[[dynamic_plugins]] activation specs instead; no dynamic plugins will be "
                "activated. Continuing with static observability only."
            )
            return []
    if raw_specs is None:
        return []
    if not isinstance(raw_specs, list):
        logger.warning(
            "Ignoring invalid NeMo Relay dynamic_plugins config: expected an array of plugin specs"
        )
        return []

    specs: list[dict[str, Any]] = []
    invalid = False
    for index, raw_spec in enumerate(raw_specs):
        if not isinstance(raw_spec, dict):
            logger.warning(
                "Invalid NeMo Relay dynamic_plugins[%d]: expected an object", index
            )
            invalid = True
            continue
        plugin_id = raw_spec.get("plugin_id")
        kind = raw_spec.get("kind")
        manifest_ref = raw_spec.get("manifest_ref")
        config = raw_spec.get("config", {})
        environment_ref = raw_spec.get("environment_ref")
        if not isinstance(plugin_id, str) or not plugin_id.strip():
            logger.warning(
                "Invalid NeMo Relay dynamic_plugins[%d]: plugin_id is required", index
            )
            invalid = True
            continue
        if kind not in {"rust_dynamic", "worker"}:
            logger.warning(
                "Invalid NeMo Relay dynamic_plugins[%d]: kind must be rust_dynamic or worker",
                index,
            )
            invalid = True
            continue
        if not isinstance(manifest_ref, str) or not manifest_ref.strip():
            logger.warning(
                "Invalid NeMo Relay dynamic_plugins[%d]: manifest_ref is required", index
            )
            invalid = True
            continue
        if not isinstance(config, dict):
            logger.warning(
                "Invalid NeMo Relay dynamic_plugins[%d]: config must be an object", index
            )
            invalid = True
            continue
        if environment_ref is not None and (
            not isinstance(environment_ref, str) or not environment_ref.strip()
        ):
            logger.warning(
                "Invalid NeMo Relay dynamic_plugins[%d]: environment_ref must be a "
                "non-empty string",
                index,
            )
            invalid = True
            continue
        spec: dict[str, Any] = {
            "plugin_id": plugin_id.strip(),
            "kind": kind,
            "manifest_ref": _config_relative_path(manifest_ref.strip(), plugins_toml_path),
            "config": config,
        }
        if environment_ref is not None:
            spec["environment_ref"] = _config_relative_path(
                environment_ref.strip(), plugins_toml_path
            )
        specs.append(spec)
    if invalid:
        logger.error(
            "NeMo Relay dynamic plugin configuration is invalid; no dynamic plugins "
            "will be activated. Continuing with static observability only."
        )
        return []
    return specs


def _config_relative_path(value: str, plugins_toml_path: str) -> str:
    """Resolve a plugin path relative to its physical ``plugins.toml`` file."""
    path = Path(value)
    if path.is_absolute():
        return str(path)
    config_path = Path(plugins_toml_path) if plugins_toml_path else Path.cwd() / "plugins.toml"
    if not config_path.is_absolute():
        config_path = Path.cwd() / config_path
    return os.path.abspath(config_path.parent / path)


def _flush_relay_subscribers(nemo_relay: Any) -> None:
    subscribers = getattr(nemo_relay, "subscribers", None)
    flush = getattr(subscribers, "flush", None)
    if callable(flush):
        flush()


def _load_plugins_config(path: str) -> dict[str, Any] | None:
    if not path:
        return None
    try:
        return tomllib.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:
        logger.debug("NeMo Relay plugins.toml load failed: %s", exc, exc_info=True)
        return None


def _enabled_component_config(
    plugins_config: dict[str, Any] | None,
    kind: str,
) -> dict[str, Any] | None:
    if not isinstance(plugins_config, dict):
        return None
    components = plugins_config.get("components")
    if not isinstance(components, list):
        return None
    for component in components:
        if not isinstance(component, dict):
            continue
        if component.get("kind") != kind or not component.get("enabled", True):
            continue
        config = component.get("config")
        return config if isinstance(config, dict) else {}
    return None


def _observability_exporter_enabled(
    plugins_config: dict[str, Any] | None,
    exporter_name: str,
) -> bool:
    observability_config = _enabled_component_config(plugins_config, "observability")
    if not isinstance(observability_config, dict):
        return False
    exporter_config = observability_config.get(exporter_name)
    if not isinstance(exporter_config, dict):
        return False
    return exporter_config.get("enabled", True) is not False


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def _atif_subagent_export_mode() -> str:
    mode = _env("HERMES_NEMO_RELAY_ATIF_SUBAGENT_EXPORT_MODE").lower()
    return "all" if mode == "all" else "embedded"


def _env_bool(name: str) -> bool:
    return _env(name).lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    raw = _env(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _session_id(kwargs: dict[str, Any]) -> str:
    return str(kwargs.get("session_id") or kwargs.get("parent_session_id") or "default")


def _child_session_id(kwargs: dict[str, Any]) -> str:
    return str(kwargs.get("child_session_id") or "")


def _subagent_child_metadata(
    kwargs: dict[str, Any],
    parent_metadata: dict[str, Any],
) -> dict[str, Any]:
    child_session_id = _child_session_id(kwargs)
    metadata = {
        "session_id": child_session_id,
        "trajectory_id": child_session_id,
        "nemo_relay_scope_role": "subagent",
    }
    for target, source in (
        ("subagent_id", "child_subagent_id"),
        ("child_session_id", "child_session_id"),
        ("child_subagent_id", "child_subagent_id"),
        ("child_role", "child_role"),
        ("parent_session_id", "parent_session_id"),
        ("parent_turn_id", "parent_turn_id"),
        ("parent_subagent_id", "parent_subagent_id"),
        ("parent_trajectory_id", "parent_trajectory_id"),
        ("telemetry_schema_version", "telemetry_schema_version"),
    ):
        value = parent_metadata.get(source)
        if value is not None:
            metadata[target] = value
    return metadata


def _metadata(kwargs: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "telemetry_schema_version",
        "session_id",
        "platform",
        "task_id",
        "turn_id",
        "api_request_id",
        "tool_call_id",
        "parent_session_id",
        "parent_turn_id",
        "parent_subagent_id",
        "child_session_id",
        "child_subagent_id",
        "child_role",
        "child_status",
        "provider",
        "model",
        "api_mode",
        "status",
        "reason",
    )
    metadata = {
        key: _jsonable(kwargs[key])
        for key in keys
        if key in kwargs and kwargs[key] is not None
    }
    if "session_id" in metadata:
        metadata.setdefault("trajectory_id", metadata["session_id"])
    if "parent_session_id" in metadata:
        metadata.setdefault("parent_trajectory_id", metadata["parent_session_id"])
    if "child_session_id" in metadata:
        metadata.setdefault("child_trajectory_id", metadata["child_session_id"])
    return metadata


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    try:
        if hasattr(value, "model_dump"):
            return _jsonable(value.model_dump(mode="json"))
    except Exception:
        pass
    try:
        if hasattr(value, "__dict__"):
            return _jsonable(vars(value))
    except Exception:
        pass
    try:
        return json.loads(json.dumps(value, default=str))
    except Exception:
        return str(value)


<<<<<<< HEAD
def _json_semantically_equal(left: Any, right: Any) -> bool:
    """Compare JSON-compatible values without conflating booleans and numbers."""
    try:
        options = {"ensure_ascii": False, "sort_keys": True, "separators": (",", ":")}
        return json.dumps(_jsonable(left), **options) == json.dumps(_jsonable(right), **options)
    except (TypeError, ValueError):
        return False


def _value(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _original_downstream_error(exc: Exception) -> BaseException:
    # Moor wraps downstream execution failures in a local/private exception
    # class, so detect the wrapper by shape instead of importing it here.
    original = getattr(exc, "original", None)
    if exc.__class__.__name__ == "_DownstreamExecutionError" and isinstance(original, BaseException):
        return original
    return exc


def _is_relay_wrapped_callback_error(exc: Exception, callback_error: Exception | None) -> bool:
    # NeMo Relay re-wraps a failing callback as ``RuntimeError("internal error:
    # <ClassName>: <message>")``. Match by prefix rather than exact equality so a
    # trailing traceback/suffix in a future Relay version doesn't silently defeat
    # the unwrap; the class-name + message prefix still discriminates the real
    # downstream failure from unrelated Relay-internal errors. If Relay drops the
    # leading ``internal error:`` shape entirely, this returns False and Moor
    # falls back to surfacing Relay's error (the pre-fix behavior) rather than
    # masking it.
    if callback_error is None or not isinstance(exc, RuntimeError):
        return False
    expected = f"internal error: {callback_error.__class__.__name__}: {callback_error}"
    return str(exc).startswith(expected)


def _llm_response_payload(response: Any) -> Any:
    """Return the LLM response shape NeMo Relay's ATIF conversion expects."""
    payload = _jsonable(response)
    if isinstance(payload, dict) and "assistant_message" in payload:
        return payload

    choices = _value(response, "choices")
    if choices is None and isinstance(payload, dict):
        choices = payload.get("choices")
    first_choice = choices[0] if isinstance(choices, list) and choices else None
    message = _value(first_choice, "message")
    finish_reason = _value(first_choice, "finish_reason")

    assistant_message: dict[str, Any] = {"role": "assistant", "content": ""}
    if message is not None:
        assistant_message["role"] = _value(message, "role", "assistant") or "assistant"
        content = _value(message, "content")
        if content is not None:
            assistant_message["content"] = _jsonable(content)
        tool_calls = _tool_calls_payload(_value(message, "tool_calls"))
        if tool_calls:
            assistant_message["tool_calls"] = tool_calls
        reasoning = _value(message, "reasoning_content")
        if reasoning is not None:
            assistant_message["reasoning_content"] = _jsonable(reasoning)
    elif isinstance(payload, dict):
        assistant_message["content"] = payload.get("content") or payload.get("output_text") or ""

    return {
        "model": _value(response, "model", payload.get("model") if isinstance(payload, dict) else None),
        "assistant_message": assistant_message,
        "finish_reason": finish_reason,
        "usage": _jsonable(_value(response, "usage", payload.get("usage") if isinstance(payload, dict) else None)),
    }


def _tool_calls_payload(tool_calls: Any) -> list[dict[str, Any]]:
    if not isinstance(tool_calls, list):
        return []
    normalized: list[dict[str, Any]] = []
    for call in tool_calls:
        function = _value(call, "function")
        normalized.append(
            {
                "id": _value(call, "id"),
                "type": _value(call, "type", "function") or "function",
                "function": {
                    "name": _value(function, "name"),
                    "arguments": _value(function, "arguments"),
                },
            }
        )
    return normalized


=======
>>>>>>> upstream/main
def _safe(fn) -> None:
    try:
        fn()
    except Exception as exc:
        logger.debug("NeMo Relay hook handling failed: %s", exc, exc_info=True)


def _resolve_awaitable(value: Any) -> Any:
    if not inspect.isawaitable(value):
        return value
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(value)

    result: dict[str, Any] = {}
    error: dict[str, BaseException] = {}

    def _runner() -> None:
        try:
            result["value"] = asyncio.run(value)
        except BaseException as exc:  # pragma: no cover - re-raised below
            error["exc"] = exc

    thread = threading.Thread(
        target=_runner,
        name="hermes-nemo-relay-awaitable",
        daemon=True,
    )
    thread.start()
    thread.join()
    if "exc" in error:
        raise error["exc"]
    return result.get("value")


def reset_for_tests() -> None:
    relay_runtime.SESSION_COORDINATOR.unregister_session_initializer(
        _SESSION_INITIALIZER_NAME
    )
    with _LOCK:
        runtimes = list(_RUNTIMES.values())
        _RUNTIMES.clear()
    for runtime in runtimes:
        if isinstance(runtime, _Runtime):
            runtime.shutdown()
    _PLUGIN_CONFIGURATION.reset_for_tests()
