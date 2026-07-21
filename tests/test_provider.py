from app.config import Settings


def _s(**kw) -> Settings:
    return Settings(_env_file=None, **kw)


def test_auto_prefers_groq_then_anthropic_then_mock():
    assert _s(llm_provider="auto").active_provider == "mock"
    assert _s(llm_provider="auto", anthropic_api_key="a").active_provider == "anthropic"
    assert _s(llm_provider="auto", groq_api_key="g").active_provider == "groq"
    # Groq wins over Anthropic under auto.
    assert (
        _s(llm_provider="auto", groq_api_key="g", anthropic_api_key="a").active_provider
        == "groq"
    )


def test_explicit_provider_without_key_falls_back_to_mock():
    assert _s(llm_provider="groq").active_provider == "mock"
    assert _s(llm_provider="anthropic").active_provider == "mock"
    assert _s(llm_provider="mock", groq_api_key="g").active_provider == "mock"


def test_explicit_provider_with_key():
    assert _s(llm_provider="groq", groq_api_key="g").active_provider == "groq"
    assert _s(llm_provider="anthropic", anthropic_api_key="a").active_provider == "anthropic"


def test_llm_enabled_flag():
    assert _s(llm_provider="auto").llm_enabled is False
    assert _s(llm_provider="auto", groq_api_key="g").llm_enabled is True
