import asyncio
import logging

logger = logging.getLogger(__name__)

_PROVIDER_DEFAULTS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-haiku-4-5-20251001",
    "google": "gemini-2.0-flash",
}


async def llm_complete(
    provider: str,
    api_key: str,
    model: str,
    messages: list[dict],
    max_tokens: int = 2048,
) -> str:
    """Send a completion request to the configured LLM provider.

    Lazy-imports the provider SDK so uninstalled providers don't break imports.
    """
    effective_model = model or _PROVIDER_DEFAULTS.get(provider, "")

    if provider == "openai":
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=api_key)
        resp = await client.chat.completions.create(
            model=effective_model,
            messages=messages,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content or ""

    elif provider == "anthropic":
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=api_key)
        system = ""
        user_messages = []
        for m in messages:
            if m["role"] == "system":
                system = m["content"]
            else:
                user_messages.append(m)
        resp = await client.messages.create(
            model=effective_model,
            max_tokens=max_tokens,
            system=system,
            messages=user_messages,
        )
        return resp.content[0].text if resp.content else ""

    elif provider == "google":
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        gm = genai.GenerativeModel(effective_model)
        prompt = "\n\n".join(m["content"] for m in messages)
        resp = await asyncio.to_thread(gm.generate_content, prompt)
        return resp.text or ""

    raise ValueError(f"Unknown LLM provider: {provider!r}. Choose openai, anthropic, or google.")
