"""Provider registry."""

from __future__ import annotations

from app.ai.providers.base import AIProvider

PROVIDER_NAMES = ("bedrock", "local-fallback")


def get_provider(name: str) -> AIProvider:
    if name == "bedrock":
        from app.ai.providers.bedrock import BedrockProvider

        return BedrockProvider()
    if name == "local-fallback":
        from app.ai.providers.local_fallback import LocalFallbackProvider

        return LocalFallbackProvider()
    raise ValueError(f"Unknown AI provider: {name!r} (expected one of {PROVIDER_NAMES})")
