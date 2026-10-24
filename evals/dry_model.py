"""Deterministic stand-in for Bedrock, used by the evals' --mode dry and by tests.

It encodes the *policy the system prompt asks for* (call the tool for files, never invent text),
so dry runs verify the wiring (schema, tool result handling, error paths), NOT model judgement.
Use --mode live for evidence about the real model.
"""

import json
import re
from typing import Any

from strands.models import Model

FILE_RE = re.compile(r"(\S+\.(?:png|jpe?g|tiff?|pdf|docx?))", re.I)


def _text_of(msg: dict) -> str:
    out = []
    for b in msg.get("content", []):
        if "text" in b:
            out.append(b["text"])
        if "toolResult" in b:
            for c in b["toolResult"]["content"]:
                out.append(c.get("text") or json.dumps(c.get("json")))
    return "\n".join(out)


class DryRunModel(Model):
    def update_config(self, **kw): ...
    def get_config(self): return {}
    async def structured_output(self, *a, **kw):  # pragma: no cover
        raise NotImplementedError
        yield

    def _reply(self, messages, tool_specs) -> tuple[str, dict | None]:
        last = messages[-1]
        if any("toolResult" in b for b in last.get("content", [])):
            data = json.loads(_text_of(last))
            if not data["ok"]:
                return f"I couldn't read that document: {data['error']} Please send the text or a clearer file.", None
            warn = f" Warning: {data['warning']}" if data.get("warning") else ""
            return "Plain-language version:\n" + data["text"] + warn, None
        user = _text_of(messages[0] if len(messages) == 1 else last)
        m = FILE_RE.search(user)
        if m and any(t.get("name") == "read_notice_document" for t in (tool_specs or [])):
            return "", {"name": "read_notice_document", "input": {"source": m.group(1)}}
        if m:
            return "I can't open image or PDF files, only text. Please paste the notice text.", None
        return "Plain-language version:\n" + user.split("\n", 1)[-1], None

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kw) -> Any:
        text, call = self._reply(messages, tool_specs)
        usage = {"metadata": {"usage": {"inputTokens": 1, "outputTokens": 1, "totalTokens": 2},
                              "metrics": {"latencyMs": 1}}}
        yield {"messageStart": {"role": "assistant"}}
        if call:
            yield {"contentBlockStart": {"start": {"toolUse": {"toolUseId": "t1", "name": call["name"]}}}}
            yield {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(call["input"])}}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "tool_use"}}
        else:
            yield {"contentBlockStart": {"start": {}}}
            yield {"contentBlockDelta": {"delta": {"text": text}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "end_turn"}}
        yield usage
