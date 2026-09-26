"""OpenCode free-tier client fingerprinting and tool cloaking.

OpenCode's Zen/Free relay enforces strict client identity checks:
1. Requests must include the canonical lowercase file-search quartet
   ("bash", "glob", "grep", "read") in `tools`.
2. Missing tools or tool names with differing casing (e.g., "Bash", "Read")
   without canonicalization trigger HTTP 403 FreeTierError:
   "OpenCode's free tier can only be used from within OpenCode".
3. Responses requests replaying prior-turn reasoning blocks from pooled
   proxy accounts fail with HTTP 400 (encrypted_content verification failure).
4. Free-tier requests must stream (stream=True).

This module provides:
- Tool canonicalization (case unification and duplicate elimination).
- Decoy tool injection for missing quartet members.
- Reverse unaliasing so the caller's original tool names are preserved.
- Prior reasoning item stripping for multi-turn Responses API calls.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

OPENCODE_FINGERPRINT_TOOLS: tuple[str, ...] = ("bash", "glob", "grep", "read")

_DECOY_TOOL_DESCRIPTION = "This tool is currently unavailable and must not be used."


def fingerprint_tool_key(name: Any) -> str:
    """Return canonical lowercase name if `name` is a quartet member, else empty string."""
    if not isinstance(name, str):
        return ""
    cleaned = name.strip().lower()
    return cleaned if cleaned in OPENCODE_FINGERPRINT_TOOLS else ""


def tool_name_of(tool: Any) -> str:
    """Extract tool name from flat ({name}) or chat ({function: {name}}) shapes."""
    if not isinstance(tool, dict):
        if hasattr(tool, "name") and isinstance(getattr(tool, "name"), str):
            return getattr(tool, "name").strip()
        fn = getattr(tool, "function", None)
        if fn is not None and hasattr(fn, "name") and isinstance(getattr(fn, "name"), str):
            return getattr(fn, "name").strip()
        return ""

    raw_name = tool.get("name")
    if isinstance(raw_name, str) and raw_name.strip():
        return raw_name.strip()

    fn = tool.get("function")
    if isinstance(fn, dict):
        fn_name = fn.get("name")
        if isinstance(fn_name, str) and fn_name.strip():
            return fn_name.strip()

    return ""


def conceal_fingerprint_tool_names(
    tools: Optional[Sequence[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Canonicalize fingerprint quartet members to lowercase and deduplicate them.

    Returns:
        tuple of (canonicalized_tools, rename_map), where rename_map maps
        canonical_sent_name -> original_caller_name.
    """
    rename_map: dict[str, str] = {}
    if not tools:
        return [], rename_map

    seen_quartet: set[str] = set()
    out: list[dict[str, Any]] = []

    for tool in tools:
        if not isinstance(tool, dict):
            out.append(tool)
            continue

        current_name = tool_name_of(tool)
        canonical_key = fingerprint_tool_key(current_name)
        if not canonical_key:
            out.append(tool)
            continue

        if canonical_key in seen_quartet:
            continue
        seen_quartet.add(canonical_key)

        if current_name != canonical_key:
            rename_map[canonical_key] = current_name
            tool_copy = dict(tool)
            if "function" in tool_copy and isinstance(tool_copy["function"], dict):
                fn_copy = dict(tool_copy["function"])
                fn_copy["name"] = canonical_key
                tool_copy["function"] = fn_copy
            else:
                tool_copy["name"] = canonical_key
            out.append(tool_copy)
        else:
            out.append(tool)

    return out, rename_map


def append_missing_fingerprint_tools(
    tools: Optional[Sequence[dict[str, Any]]],
    *,
    flat: bool,
) -> list[dict[str, Any]]:
    """Append genuinely missing quartet members as inert decoy tools."""
    tool_list = list(tools) if tools else []
    existing_keys = {fingerprint_tool_key(tool_name_of(t)) for t in tool_list}

    for name in OPENCODE_FINGERPRINT_TOOLS:
        if name in existing_keys:
            continue
        if flat:
            tool_list.append({
                "type": "function",
                "name": name,
                "description": _DECOY_TOOL_DESCRIPTION,
                "parameters": {"type": "object", "properties": {}},
            })
        else:
            tool_list.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": _DECOY_TOOL_DESCRIPTION,
                    "parameters": {"type": "object", "properties": {}},
                },
            })
        existing_keys.add(name)

    return tool_list


def retarget_tool_choice(tool_choice: Any, rename_map: Mapping[str, str]) -> Any:
    """Retarget tool_choice referencing an original quartet spelling to lowercase."""
    if not isinstance(tool_choice, dict) or not rename_map:
        return tool_choice

    choice_name = tool_choice.get("name")
    if isinstance(choice_name, str):
        key = fingerprint_tool_key(choice_name)
        if key and key in rename_map:
            updated = dict(tool_choice)
            updated["name"] = key
            return updated

    fn = tool_choice.get("function")
    if isinstance(fn, dict) and isinstance(fn.get("name"), str):
        key = fingerprint_tool_key(fn["name"])
        if key and key in rename_map:
            updated_fn = dict(fn)
            updated_fn["name"] = key
            updated = dict(tool_choice)
            updated["function"] = updated_fn
            return updated

    return tool_choice


def apply_fingerprint_tools(
    tools: Optional[Sequence[dict[str, Any]]],
    *,
    flat: bool,
    tool_choice: Any = None,
) -> tuple[list[dict[str, Any]], Any, dict[str, str]]:
    """Apply complete OpenCode fingerprint cloaking to a tool list.

    Returns:
        (fingerprinted_tools, adjusted_tool_choice, rename_map)
    """
    had_client_tools = bool(tools and len(tools) > 0)
    canonical_tools, rename_map = conceal_fingerprint_tool_names(tools)
    final_tools = append_missing_fingerprint_tools(canonical_tools, flat=flat)
    adjusted_choice = retarget_tool_choice(tool_choice, rename_map)

    if adjusted_choice is None:
        if flat:
            adjusted_choice = "auto"
        elif not had_client_tools:
            adjusted_choice = "none"

    return final_tools, adjusted_choice, rename_map


def restore_tool_names(payload: Any, rename_map: Optional[Mapping[str, str]]) -> Any:
    """Restore caller tool spellings across responses, event streams, and tool calls."""
    if not rename_map or payload is None:
        return payload

    # If it is a ToolCall object from agent.transports.types
    if hasattr(payload, "name") and getattr(payload, "name") in rename_map:
        original = rename_map[getattr(payload, "name")]
        try:
            # dataclass / object copy with replaced name
            setattr(payload, "name", original)
        except Exception:
            pass
        return payload

    if isinstance(payload, list):
        return [restore_tool_names(item, rename_map) for item in payload]

    if not isinstance(payload, dict):
        return payload

    out = dict(payload)

    # 1. Responses output items
    if "output" in out and isinstance(out["output"], list):
        restored_output = []
        for item in out["output"]:
            if isinstance(item, dict) and item.get("type") == "function_call":
                raw_name = item.get("name")
                if isinstance(raw_name, str) and raw_name in rename_map:
                    item_copy = dict(item)
                    item_copy["name"] = rename_map[raw_name]
                    restored_output.append(item_copy)
                    continue
            restored_output.append(item)
        out["output"] = restored_output

    # 2. Responses SSE item
    if "item" in out and isinstance(out["item"], dict):
        item = out["item"]
        if item.get("type") == "function_call":
            raw_name = item.get("name")
            if isinstance(raw_name, str) and raw_name in rename_map:
                item_copy = dict(item)
                item_copy["name"] = rename_map[raw_name]
                out["item"] = item_copy

    # 3. Chat completions choices
    if "choices" in out and isinstance(out["choices"], list):
        restored_choices = []
        for choice in out["choices"]:
            if not isinstance(choice, dict):
                restored_choices.append(choice)
                continue
            choice_copy = dict(choice)
            for holder in ("message", "delta"):
                msg = choice_copy.get(holder)
                if isinstance(msg, dict) and isinstance(msg.get("tool_calls"), list):
                    msg_copy = dict(msg)
                    restored_calls = []
                    for tc in msg.get("tool_calls", []):
                        if isinstance(tc, dict) and isinstance(tc.get("function"), dict):
                            fn = tc["function"]
                            fn_name = fn.get("name")
                            if isinstance(fn_name, str) and fn_name in rename_map:
                                tc_copy = dict(tc)
                                fn_copy = dict(fn)
                                fn_copy["name"] = rename_map[fn_name]
                                tc_copy["function"] = fn_copy
                                restored_calls.append(tc_copy)
                                continue
                        restored_calls.append(tc)
                    msg_copy["tool_calls"] = restored_calls
                    choice_copy[holder] = msg_copy
            restored_choices.append(choice_copy)
        out["choices"] = restored_choices

    # 4. Claude content_block_start
    if out.get("type") == "content_block_start":
        block = out.get("content_block")
        if isinstance(block, dict) and block.get("type") == "tool_use":
            block_name = block.get("name")
            if isinstance(block_name, str) and block_name in rename_map:
                block_copy = dict(block)
                block_copy["name"] = rename_map[block_name]
                out["content_block"] = block_copy

    # 5. Claude content array
    if "content" in out and isinstance(out["content"], list):
        restored_content = []
        for block in out["content"]:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                block_name = block.get("name")
                if isinstance(block_name, str) and block_name in rename_map:
                    block_copy = dict(block)
                    block_copy["name"] = rename_map[block_name]
                    restored_content.append(block_copy)
                    continue
            restored_content.append(block)
        out["content"] = restored_content

    return out


def strip_prior_reasoning_items(input_items: Optional[Sequence[Any]]) -> list[Any]:
    """Strip prior reasoning items and encrypted_content from Responses API input items.

    OpenCode's free and proxy backends fail on replaying encrypted continuation
    tokens that originated from another upstream pooled credential.
    """
    if not input_items:
        return []

    cleaned: list[Any] = []
    for item in input_items:
        if not isinstance(item, dict):
            cleaned.append(item)
            continue

        item_type = item.get("type")
        if item_type == "reasoning":
            continue

        item_copy = dict(item)
        item_copy.pop("encrypted_content", None)

        if "content" in item_copy and isinstance(item_copy["content"], list):
            content_blocks = []
            for block in item_copy["content"]:
                if isinstance(block, dict) and block.get("type") == "reasoning":
                    continue
                content_blocks.append(block)
            item_copy["content"] = content_blocks

        cleaned.append(item_copy)

    return cleaned
