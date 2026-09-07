"""Anthropic provider via the official SDK. Model name comes from the environment (LLM_MODEL) - never hard-coded.
Thinking is left at the model default (adaptive on current models); effort is configurable. Output is requested
as JSON via the system prompt and parsed defensively; the validator decides whether it is usable."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from director.contracts.reasoning import EvidenceBundle
from director.reasoning.prompts import REPAIR_PROMPT, SYSTEM_PROMPT
from director.reasoning.provider import Budget, ProviderResult, bundle_to_prompt

log = logging.getLogger("director.llm")
JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model: str, api_key: str, *, effort: str = "medium", timeout: float = 120.0):
        import anthropic

        if not model:
            raise ValueError(
                "LLM_MODEL must be set (check the current model list in the Anthropic docs on the day of deployment)"
            )
        self.model = model
        self.effort = effort
        self._anthropic = anthropic
        self._client = anthropic.Anthropic(api_key=api_key or None, timeout=timeout, max_retries=2)

    def generate(
        self,
        bundle: EvidenceBundle,
        schema: dict[str, Any],
        budget: Budget,
        *,
        repair_errors: list[str] | None = None,
        previous: str | None = None,
    ) -> ProviderResult:
        user = (
            "EvidenceBundle (JSON):\n"
            + bundle_to_prompt(bundle, budget)
            + "\n\nSchemat odpowiedzi (JSON Schema):\n"
            + json.dumps(schema, ensure_ascii=False)
        )
        messages: list[dict[str, Any]] = [{"role": "user", "content": user}]
        if repair_errors and previous:
            messages += [
                {"role": "assistant", "content": previous},
                {"role": "user", "content": REPAIR_PROMPT.format(errors="; ".join(repair_errors[:8]))},
            ]
        try:
            resp = self._client.messages.create(
                model=self.model,
                max_tokens=budget.max_output_tokens,
                system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
                output_config={"effort": self.effort},
                messages=messages,
            )
        except self._anthropic.RateLimitError as exc:
            return ProviderResult(None, "", self.model, error=f"rate limited: {exc}")
        except self._anthropic.APIStatusError as exc:
            return ProviderResult(None, "", self.model, error=f"api error {exc.status_code}: {exc.message}")
        except self._anthropic.APIConnectionError as exc:
            return ProviderResult(None, "", self.model, error=f"connection error: {exc}")
        if resp.stop_reason == "refusal":
            return ProviderResult(
                None,
                "",
                self.model,
                tokens_in=resp.usage.input_tokens,
                tokens_out=resp.usage.output_tokens,
                error="model refused (stop_reason=refusal)",
            )
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        raw = _extract_json(text)
        return ProviderResult(
            raw,
            text,
            self.model,
            tokens_in=resp.usage.input_tokens,
            tokens_out=resp.usage.output_tokens,
            error=None if raw is not None else "no JSON object in model output",
            meta={
                "stop_reason": resp.stop_reason,
                "cache_read": getattr(resp.usage, "cache_read_input_tokens", None),
            },
        )


def _extract_json(text: str) -> dict[str, Any] | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = JSON_BLOCK.search(text)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None


def build_provider(settings) -> Any:
    from director.reasoning.provider import FakeProvider, NoProvider

    if settings.llm_provider == "anthropic":
        return AnthropicProvider(settings.llm_model, settings.llm_api_key)
    if settings.llm_provider == "fake":
        return FakeProvider()
    return NoProvider()
