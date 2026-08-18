"""Validated layered settings without resolving secret references."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence, Set
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Any, TypeVar

import yaml
from pydantic import BaseModel, SecretBytes, SecretStr, ValidationError

__all__ = ["ConfigLoadError", "RedactedSettingsSummary", "SettingsLoader", "SettingsSource"]

SettingsT = TypeVar("SettingsT", bound=BaseModel)
SUMMARY_SAFE = "summary_safe"
SECRET_REFERENCE = "secret_reference"
REDACTED = "<redacted>"


class ConfigLoadError(ValueError):
    """A safe configuration-boundary error."""

    def __init__(self, reason: str, field_path: str | None = None) -> None:
        self.reason = reason
        self.field_path = field_path
        location = f" at {field_path}" if field_path else ""
        super().__init__(f"configuration {reason}{location}")


class SourceKind(StrEnum):
    FILE = "file"
    ENV = "env"
    VALUES = "values"


@dataclass(frozen=True, slots=True)
class SettingsSource:
    """One settings layer; later sources override earlier ones."""

    kind: SourceKind
    location: str | None = None
    prefix: str = ""
    values: Mapping[str, Any] | None = None

    @classmethod
    def file(cls, path: str | Path) -> SettingsSource:
        return cls(SourceKind.FILE, location=str(path))

    @classmethod
    def env(cls, prefix: str = "", values: Mapping[str, str] | None = None) -> SettingsSource:
        return cls(SourceKind.ENV, prefix=prefix, values=values)

    @classmethod
    def mapping(cls, values: Mapping[str, Any]) -> SettingsSource:
        return cls(SourceKind.VALUES, values=values)


@dataclass(frozen=True, slots=True)
class RedactedSettingsSummary:
    values: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))


class SettingsLoader:
    """Load deterministic file/env layers and validate at the Pydantic boundary."""

    def load(self, schema: type[SettingsT], sources: Sequence[SettingsSource]) -> SettingsT:
        merged: dict[str, Any] = {}
        for source in sources:
            merged.update(self._read(source))
        try:
            return schema.model_validate(merged)
        except ValidationError as exc:
            first = exc.errors(include_url=False)[0]
            path = ".".join(str(part) for part in first.get("loc", ())) or None
            raise ConfigLoadError(str(first.get("type", "invalid")), path) from None

    def summarize(self, settings: BaseModel) -> RedactedSettingsSummary:
        return RedactedSettingsSummary(self._summarize_model(settings))

    def _read(self, source: SettingsSource) -> dict[str, Any]:
        if source.kind is SourceKind.FILE:
            return self._read_file(source.location)
        if source.kind is SourceKind.ENV:
            return self._read_env(source.prefix, source.values)
        if source.values is None:
            raise ConfigLoadError("missing_source_values")
        return dict(source.values)

    @staticmethod
    def _read_file(location: str | None) -> dict[str, Any]:
        if not location:
            raise ConfigLoadError("missing_file_path")
        try:
            text = Path(location).read_text(encoding="utf-8")
            loaded = json.loads(text) if location.endswith(".json") else yaml.safe_load(text)
        except (OSError, UnicodeError, json.JSONDecodeError, yaml.YAMLError):
            raise ConfigLoadError("unreadable_or_invalid_file") from None
        if not isinstance(loaded, dict):
            raise ConfigLoadError("file_root_not_object")
        return loaded

    @staticmethod
    def _read_env(prefix: str, values: Mapping[str, Any] | None) -> dict[str, Any]:
        environ = os.environ if values is None else values
        result: dict[str, Any] = {}
        for key, value in environ.items():
            if key.startswith(prefix):
                result[key[len(prefix) :].lower()] = value
        return result

    @classmethod
    def _summarize_model(cls, model: BaseModel) -> dict[str, object]:
        summary: dict[str, object] = {}
        for name, field in type(model).model_fields.items():
            key = field.serialization_alias or field.alias or name
            metadata = field.json_schema_extra if isinstance(field.json_schema_extra, dict) else {}
            value = getattr(model, name)
            if metadata.get(SECRET_REFERENCE) is True:
                summary[key] = cls._safe_reference(value)
            elif isinstance(value, BaseModel):
                summary[key] = cls._summarize_model(value)
            else:
                summary[key] = cls._summarize_value(value, metadata.get(SUMMARY_SAFE) is True)
        return summary

    @classmethod
    def _summarize_value(cls, value: Any, safe: bool) -> object:
        if isinstance(value, (SecretStr, SecretBytes, bytes, bytearray, memoryview)):
            return REDACTED
        if isinstance(value, BaseModel):
            return cls._summarize_model(value)
        if isinstance(value, Mapping):
            return {str(key): cls._summarize_value(item, safe) for key, item in value.items()}
        if isinstance(value, (list, tuple, Set)):
            return [cls._summarize_value(item, safe) for item in value]
        if safe and (value is None or isinstance(value, (str, int, float, bool))):
            return value
        return REDACTED

    @staticmethod
    def _safe_reference(value: Any) -> str:
        if not isinstance(value, str) or any(character.isspace() for character in value):
            return REDACTED
        if value.startswith(("env://", "file://")) and "@" not in value:
            return value
        return REDACTED
