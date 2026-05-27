import os
from dotenv import load_dotenv
import anthropic

load_dotenv()

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def chat(messages: list, system: str = None, max_tokens: int = 2000) -> str:
    client = _get_client()
    model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

    kwargs = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if system:
        kwargs["system"] = system

    response = client.messages.create(**kwargs)
    return response.content[0].text
