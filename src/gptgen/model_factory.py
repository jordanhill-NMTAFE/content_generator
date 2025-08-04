"""
Model Factory for Content Generator

This module provides functionality to instantiate different AI models
for content generation, supporting multiple providers like OpenAI, Anthropic, etc.
"""

import os
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from os import environ as env

import logging

log = logging.getLogger(__name__)


# Try to import GPT library, but make it optional
try:
    from gpt.models.openai_ import Chat as OpenAIChat
    from gpt.models.anthropic import Chat as AnthropicChat
    from gpt.models.huggingface import HuggingFaceModel

    GPT_AVAILABLE = True
except ImportError as e:
    log.warning(f"GPT library not available: {e}")
    OpenAIChat = None
    AnthropicChat = None
    HuggingFaceModel = None
    GPT_AVAILABLE = False


async def get_anthropic_models():
    """Fetch available Anthropic models."""
    if not GPT_AVAILABLE:
        return {}

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=env.get("ANTHROPIC_API_KEY"))
        models = [model.id for model in client.models.list().data]
        return {id: "anthropic" for id in models}
    except Exception as e:
        log.error(f"Failed to fetch Anthropic models: {e}")
        return {}


async def get_openai_models():
    """Fetch available OpenAI models."""
    if not GPT_AVAILABLE:
        return {}

    try:
        import openai

        client = openai.OpenAI(api_key=env.get("OPENAI_API_KEY"))
        models = [model.id for model in client.models.list().data]
        return {id: "openai" for id in models}
    except Exception as e:
        log.error(f"Failed to fetch OpenAI models: {e}")
        return {}


async def build_supported_models():
    """Build a dictionary of supported models with their providers."""
    # Define default static models that are always available
    static_models = {
        "gpt-4.1-nano-2025-04-14": "openai",
        "gpt-4o-mini": "openai",
        "gpt-4o": "openai",
        "gpt-4-turbo": "openai",
        "claude-3-5-sonnet": "anthropic",
        "claude-3-opus": "anthropic",
        "claude-3-haiku": "anthropic",
        "meta-llama/Llama-3.2-1B-Instruct": "huggingface",
        "meta-llama/Llama-3.2-3B-Instruct": "huggingface",
        "meta-llama/Llama-3.2-11B-Vision-Instruct": "huggingface",
        "deepseek-ai/DeepSeek-V3": "huggingface",
    }

    # Check for cached models
    cache_file = os.path.join(
        os.path.expanduser("~"), ".content_generator_models_cache.json"
    )
    try:
        if os.path.exists(cache_file):
            with open(cache_file, "r") as f:
                cache_data = json.load(f)
                # Check if cache is still valid (less than 24 hours old)
                cache_time = datetime.fromisoformat(cache_data.get("timestamp", ""))
                if datetime.now() - cache_time < timedelta(hours=24):
                    log.debug("Using cached models list")
                    return cache_data.get("models", static_models)
    except Exception as e:
        log.warning(f"Error reading cache: {e}")

    try:
        # Run API calls concurrently
        openai_task = asyncio.create_task(get_openai_models())
        anthropic_task = asyncio.create_task(get_anthropic_models())

        # Wait for both tasks to complete
        openai_models_dict, anthropic_models_dict = await asyncio.gather(
            openai_task, anthropic_task
        )

        # Combine with static models
        models_dict = {
            **openai_models_dict,
            **anthropic_models_dict,
            **static_models,
        }

        # Cache the results
        try:
            with open(cache_file, "w") as f:
                json.dump(
                    {"timestamp": datetime.now().isoformat(), "models": models_dict}, f
                )
        except Exception as e:
            log.warning(f"Failed to cache models: {e}")

        return models_dict
    except Exception as e:
        # Handle failure in offline mode
        log.warning(f"Failed to fetch online models, running in offline mode: {e}")
        return static_models


def get_model_provider(model_id: str) -> Tuple[str, str]:
    """
    Get the provider for a given model ID.

    Args:
        model_id: The model identifier

    Returns:
        Tuple of (model_id, provider)

    Raises:
        ValueError: If model is not supported
    """
    # Initialize models synchronously
    try:
        models_dict = asyncio.run(build_supported_models())
    except Exception:
        # Fallback to static models if async fails
        models_dict = {
            "gpt-4.1-nano-2025-04-14": "openai",
            "gpt-4o-mini": "openai",
            "gpt-4o": "openai",
            "gpt-4-turbo": "openai",
            "claude-3-5-sonnet": "anthropic",
            "claude-3-opus": "anthropic",
            "claude-3-haiku": "anthropic",
        }

    if model_id in models_dict:
        return model_id, models_dict[model_id]

    # Try fuzzy matching for common patterns
    if model_id.startswith("gpt-"):
        return model_id, "openai"
    elif model_id.startswith("claude-"):
        return model_id, "anthropic"
    elif "llama" in model_id.lower() or "deepseek" in model_id.lower():
        return model_id, "huggingface"

    raise ValueError(f"Unsupported model: {model_id}")


def create_model_client(model_id: str, **kwargs):
    """
    Create a model client instance based on the model ID.

    Args:
        model_id: The model identifier
        **kwargs: Additional arguments for the model client

    Returns:
        Model client instance

    Raises:
        ValueError: If model is not supported or provider not available
    """
    if not GPT_AVAILABLE:
        raise ValueError("GPT library not available")

    model_name, provider = get_model_provider(model_id)

    if provider == "openai":
        if not OpenAIChat:
            raise ValueError("OpenAI models not available")
        return OpenAIChat(
            model_name=model_name,
            max_completion_tokens=kwargs.get("max_completion_tokens", 32768),
            context=kwargs.get("context", 1),
        )
    elif provider == "anthropic":
        if not AnthropicChat:
            raise ValueError("Anthropic models not available")
        return AnthropicChat(model_name=model_name, **kwargs)
    elif provider == "huggingface":
        if not HuggingFaceModel:
            raise ValueError("HuggingFace models not available")
        return HuggingFaceModel(model_name=model_name, **kwargs)
    else:
        raise ValueError(f"Unsupported provider: {provider}")


def list_available_models():
    """List all available models."""
    try:
        models_dict = asyncio.run(build_supported_models())
        return list(models_dict.keys())
    except Exception as e:
        log.warning(f"Failed to list models: {e}")
        return [
            "gpt-4.1-nano-2025-04-14",
            "gpt-4o-mini",
            "gpt-4o",
            "claude-3-5-sonnet",
            "claude-3-opus",
            "claude-3-haiku",
        ]
