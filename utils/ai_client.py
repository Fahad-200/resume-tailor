"""
Shared Gemini helpers for model selection, retries, and actionable errors.
"""

import os
import re
from typing import List, Optional

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions


DEFAULT_MODEL = "gemini-2.5-flash"
DEFAULT_FALLBACK_MODELS = ["gemini-2.5-flash-lite", "gemini-2.0-flash"]


class GeminiServiceError(Exception):
    """Base exception for Gemini integration failures."""


class GeminiQuotaError(GeminiServiceError):
    """Raised when Gemini rejects a request because quota is unavailable."""


def _split_models(raw_value: str) -> List[str]:
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def get_model_sequence() -> List[str]:
    primary_model = os.getenv("GEMINI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    fallback_models = _split_models(
        os.getenv(
            "GEMINI_FALLBACK_MODELS",
            ",".join(DEFAULT_FALLBACK_MODELS),
        )
    )

    ordered_models: List[str] = []
    for model_name in [primary_model, *fallback_models]:
        if model_name and model_name not in ordered_models:
            ordered_models.append(model_name)

    return ordered_models


def get_primary_model() -> str:
    return get_model_sequence()[0]


def get_fallback_models() -> List[str]:
    return get_model_sequence()[1:]


def _extract_retry_delay(error_text: str) -> Optional[int]:
    match = re.search(r"retry in (\d+(?:\.\d+)?)s", error_text, flags=re.IGNORECASE)
    if not match:
        return None

    try:
        return max(1, round(float(match.group(1))))
    except ValueError:
        return None


def _is_zero_quota_error(error_text: str) -> bool:
    lowered = error_text.lower()
    return "quota exceeded" in lowered and "limit: 0" in lowered


def _build_quota_message(error_text: str, attempted_models: List[str]) -> str:
    models_text = ", ".join(attempted_models)
    retry_delay = _extract_retry_delay(error_text)

    if _is_zero_quota_error(error_text):
        return (
            "Gemini rejected the request because this API project currently has no usable quota "
            f"for the configured model(s): {models_text}. Google returned a free-tier limit of 0. "
            "This is usually a Google project or billing issue, not a bug in the app. In Google AI Studio, "
            "open the project tied to this API key and either enable billing for that project or switch to "
            "an API key from another project that already has active Gemini API quota. "
            "Changing only the prompt or UI will not fix a limit-0 response."
        )

    delay_suffix = ""
    if retry_delay is not None:
        delay_suffix = f" Google suggested retrying after about {retry_delay} seconds."

    return (
        f"Gemini rate limits were reached for model(s): {models_text}. "
        "This app makes multiple AI calls for each generation, so the free tier can be exhausted quickly. "
        "Wait a short time and try again, or enable billing for higher quotas."
        f"{delay_suffix}"
    )


def generate_text(
    prompt: str,
    *,
    max_retries: int = 1,
    response_mime_type: Optional[str] = None,
    temperature: Optional[float] = None,
) -> str:
    """
    Generate text with the configured Gemini model sequence.

    Tries the primary model first, then any configured fallbacks.
    """
    attempted_models = get_model_sequence()
    last_error: Optional[Exception] = None

    for _ in range(max_retries):
        for model_name in attempted_models:
            try:
                model = genai.GenerativeModel(model_name)

                generation_config = {}
                if response_mime_type:
                    generation_config["response_mime_type"] = response_mime_type
                if temperature is not None:
                    generation_config["temperature"] = temperature

                response = model.generate_content(
                    prompt,
                    generation_config=generation_config or None,
                )

                response_text = getattr(response, "text", "") or ""
                if response_text.strip():
                    return response_text.strip()

                last_error = GeminiServiceError(
                    f"Model '{model_name}' returned an empty response."
                )
            except google_exceptions.ResourceExhausted as exc:
                last_error = exc
            except Exception as exc:
                last_error = exc

    if isinstance(last_error, google_exceptions.ResourceExhausted):
        raise GeminiQuotaError(
            _build_quota_message(str(last_error), attempted_models)
        ) from last_error

    if isinstance(last_error, google_exceptions.GoogleAPICallError):
        raise last_error

    if last_error:
        raise GeminiServiceError(f"AI call failed: {last_error}") from last_error

    raise GeminiServiceError("AI call failed: Gemini returned no usable response.")
