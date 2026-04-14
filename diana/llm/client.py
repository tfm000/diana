import asyncio
import logging

logger = logging.getLogger(__name__)

_PROVIDER_DEFAULTS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-haiku-4-5-20251001",
    "anthropic-cli": "claude-sonnet-4-5",
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

    elif provider == "anthropic-cli":
        try:
            from claude_agent_sdk import (
                query,
                ClaudeAgentOptions,
                AssistantMessage,
                TextBlock,
                ResultMessage,
            )
        except ImportError as e:
            raise RuntimeError(
                "anthropic-cli provider requires 'claude-agent-sdk' "
                "(pip install claude-agent-sdk) and the Claude Code CLI "
                "installed with an active login (run `claude login`)."
            ) from e

        system = ""
        turns: list[str] = []
        for m in messages:
            if m["role"] == "system":
                system = m["content"]
            else:
                turns.append(f"{m['role']}: {m['content']}")
        prompt = "\n\n".join(turns)

        options = ClaudeAgentOptions(
            system_prompt=system or None,
            model=effective_model,
        )
        chunks: list[str] = []
        async for msg in query(prompt=prompt, options=options):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        chunks.append(block.text)
            elif isinstance(msg, ResultMessage) and getattr(msg, "is_error", False):
                raise RuntimeError(
                    f"claude-agent-sdk error: {getattr(msg, 'result', 'unknown')}"
                )
        return "".join(chunks)

    elif provider == "google":
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        gm = genai.GenerativeModel(effective_model)
        prompt = "\n\n".join(m["content"] for m in messages)
        resp = await asyncio.to_thread(gm.generate_content, prompt)
        return resp.text or ""

    raise ValueError(
        f"Unknown LLM provider: {provider!r}. "
        "Choose openai, anthropic, anthropic-cli, or google."
    )
