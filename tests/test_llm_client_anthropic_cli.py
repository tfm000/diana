import pytest

from diana.llm.client import llm_complete

pytest.importorskip("claude_agent_sdk")


@pytest.mark.asyncio
async def test_anthropic_cli_real_call():
    """Real end-to-end call via claude-agent-sdk.

    Requires: claude-agent-sdk installed, Node.js + Claude Code CLI installed,
    and an active `claude login` session. Skipped automatically if the SDK
    package is not importable.
    """
    messages = [
        {
            "role": "system",
            "content": "You reply with exactly one word, lowercase, no punctuation.",
        },
        {"role": "user", "content": "Say the word ping."},
    ]
    result = await llm_complete(
        provider="anthropic-cli",
        api_key="",
        model="",
        messages=messages,
        max_tokens=64,
    )
    assert isinstance(result, str)
    assert result.strip()
    assert "ping" in result.lower()
