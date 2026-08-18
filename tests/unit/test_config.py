import json
import logging

import pytest
from pydantic import BaseModel, ConfigDict, Field, SecretBytes, SecretStr, ValidationError

from seed.config import ConfigLoadError, SettingsLoader, SettingsSource

SUMMARY_SAFE = "summary_safe"
SECRET_REFERENCE = "secret_reference"


class AppSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    host: str = Field(json_schema_extra={SUMMARY_SAFE: True})
    port: int = Field(json_schema_extra={SUMMARY_SAFE: True})
    database_credential_ref: str = Field(json_schema_extra={SECRET_REFERENCE: True})
    api_token: str | None = None


def test_layered_file_and_env_and_redacted_summary(tmp_path) -> None:
    config_file = tmp_path / "settings.json"
    config_file.write_text(
        json.dumps({"host": "db", "port": 2881, "database_credential_ref": "env://DB_PASSWORD", "api_token": "canary"})
    )
    settings = SettingsLoader().load(
        AppSettings,
        [SettingsSource.file(config_file), SettingsSource.env("APP_", {"APP_PORT": "2883"})],
    )
    assert settings.port == 2883
    with pytest.raises(ValidationError):
        settings.port = 1  # type: ignore[misc]
    summary = SettingsLoader().summarize(settings).values
    assert summary["database_credential_ref"] == "env://DB_PASSWORD"
    assert summary["api_token"] == "<redacted>"
    assert "canary" not in repr(summary)


class Opaque:
    def __repr__(self) -> str:
        return "nested-canary"


class NestedSettings(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True, populate_by_name=True)
    public_name: str = Field(alias="publicName", json_schema_extra={SUMMARY_SAFE: True})
    private_key: str
    secret_text: SecretStr
    secret_bytes: SecretBytes
    raw_bytes: bytes
    api_key: str
    signing_key: str
    unknown: Opaque
    mapping: dict[str, str]
    items: list[str]
    safe_items: tuple[str, ...] = Field(json_schema_extra={SUMMARY_SAFE: True})
    reference: str = Field(json_schema_extra={SECRET_REFERENCE: True})


def test_summary_is_recursive_and_deny_by_default(caplog) -> None:
    canary = "summary-canary-71f4"
    settings = NestedSettings(
        publicName="visible",
        private_key=canary,
        secret_text=canary,
        secret_bytes=canary.encode(),
        raw_bytes=canary.encode(),
        api_key=canary,
        signing_key=canary,
        unknown=Opaque(),
        mapping={"unknown_key": canary},
        items=[canary],
        safe_items=("one", "two"),
        reference="env://DATABASE_CREDENTIAL",
    )
    summary = SettingsLoader().summarize(settings)
    with caplog.at_level(logging.INFO):
        logging.getLogger("test").info("summary=%r", summary)
    rendered = repr(summary) + caplog.text
    assert canary not in rendered and "nested-canary" not in rendered
    assert summary.values["publicName"] == "visible"
    assert summary.values["safe_items"] == ["one", "two"]
    assert summary.values["reference"] == "env://DATABASE_CREDENTIAL"
    assert summary.values["mapping"] == {"unknown_key": "<redacted>"}
    assert summary.values["items"] == ["<redacted>"]


@pytest.mark.parametrize("value", ["inline://canary", "env://BAD VALUE", b"env://VALUE", Opaque()])
def test_invalid_reference_is_redacted(value) -> None:
    class ReferenceSettings(BaseModel):
        model_config = ConfigDict(arbitrary_types_allowed=True)
        reference: object = Field(json_schema_extra={SECRET_REFERENCE: True})

    assert SettingsLoader().summarize(ReferenceSettings(reference=value)).values["reference"] == "<redacted>"


@pytest.mark.parametrize(
    ("sources", "reason"),
    [
        ([SettingsSource.file("/not/here")], "unreadable_or_invalid_file"),
        ([SettingsSource.mapping({"host": "db"})], "missing"),
        (
            [SettingsSource.mapping({"host": "db", "port": 2881, "database_credential_ref": "env://X", "extra": 1})],
            "extra_forbidden",
        ),
    ],
)
def test_invalid_sources_fail_fast(sources, reason) -> None:
    with pytest.raises(ConfigLoadError) as caught:
        SettingsLoader().load(AppSettings, sources)
    assert reason in (caught.value.reason, str(caught.value))


def test_yaml_root_must_be_mapping(tmp_path) -> None:
    path = tmp_path / "bad.yml"
    path.write_text("- item\n")
    with pytest.raises(ConfigLoadError, match="file_root_not_object"):
        SettingsLoader().load(AppSettings, [SettingsSource.file(path)])
