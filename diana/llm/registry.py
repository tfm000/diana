import logging

from diana.config import DianaConfig, LLMConfig

logger = logging.getLogger(__name__)


def get_llm_config(config: DianaConfig) -> LLMConfig | None:
    """Return LLMConfig if LLM is properly configured, else None.

    Returns None (rather than raising) so callers can silently fall back
    to rule-based processing when the LLM is not set up.
    """
    llm = config.llm
    if not llm.enabled:
        return None
    if llm.provider == "anthropic-cli":
        return llm
    if not llm.api_key or llm.api_key.startswith("${"):
        logger.warning(
            "LLM cleaning is enabled but the API key is missing or unresolved "
            "(value: %r). Falling back to rule-based cleaner.", llm.api_key
        )
        return None
    return llm
