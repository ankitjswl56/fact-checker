from __future__ import annotations

import os
from typing import TypeVar

import litellm
from pydantic import BaseModel

DEFAULT_MODEL = "gemini/gemini-3.1-flash-lite"
DEFAULT_FAST_MODEL = "gemini/gemini-3.1-flash-lite"

T = TypeVar("T", bound=BaseModel)


def _resolve_model(*, fast: bool) -> str:
    if fast:
        return os.environ.get("LLM_MODEL_FAST", DEFAULT_FAST_MODEL)
    return os.environ.get("LLM_MODEL", DEFAULT_MODEL)


async def complete_structured(
    *,
    system: str,
    user: str,
    response_model: type[T],
    fast: bool = False,
) -> T:
    """Call the configured LLM and parse its response into `response_model`."""
    model = _resolve_model(fast=fast)
    response = await litellm.acompletion(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format=response_model,
        num_retries=5,
    )
    content = response.choices[0].message.content
    return response_model.model_validate_json(content)