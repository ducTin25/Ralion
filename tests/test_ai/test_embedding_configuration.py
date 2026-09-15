import pytest

from src.config import Settings


@pytest.mark.parametrize(
    "settings",
    [
        {"use_fake_embedder": False},
        {"bge_m3_endpoint": "https://embed.test"},
        {"bge_m3_api_key": "secret"},
        {
            "use_fake_embedder": True,
            "bge_m3_endpoint": "https://embed.test",
            "bge_m3_api_key": "secret",
        },
    ],
)
def test_embedding_configuration_fails_fast_for_ambiguous_or_incomplete_resolution(settings) -> None:
    with pytest.raises(ValueError):
        Settings(_env_file=None, **settings)


@pytest.mark.parametrize(
    "settings",
    [
        {"langfuse_public_key": "public-only"},
        {"langfuse_secret_key": "secret-only"},
        {
            "langfuse_public_key": "public",
            "langfuse_secret_key": "secret",
            "langfuse_host": "http://langfuse.test",
        },
    ],
)
def test_langfuse_configuration_requires_a_complete_https_pair(settings) -> None:
    with pytest.raises(ValueError):
        Settings(_env_file=None, **settings)


def test_langfuse_complete_https_configuration_is_valid() -> None:
    settings = Settings(
        _env_file=None,
        langfuse_public_key="public",
        langfuse_secret_key="secret",
        langfuse_host="https://langfuse.test",
    )
    assert settings.langfuse_host == "https://langfuse.test"
