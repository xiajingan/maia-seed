from __future__ import annotations

import importlib
import importlib.util
import sys
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType


@contextmanager
def alternate_seed_package() -> Iterator[tuple[ModuleType, ModuleType]]:
    seed_dir = Path(__file__).parents[2] / "src" / "seed"
    prefix = f"_seed_contract_alt_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(
        prefix,
        seed_dir / "__init__.py",
        submodule_search_locations=[str(seed_dir)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("alternate seed package spec could not be created")
    package = importlib.util.module_from_spec(spec)
    sys.modules[prefix] = package
    try:
        spec.loader.exec_module(package)
        alternate_errors = importlib.import_module(f"{prefix}.errors")
        alternate_retry = importlib.import_module(f"{prefix}.retry")
        yield alternate_errors, alternate_retry
    finally:
        for module_name in tuple(sys.modules):
            if module_name == prefix or module_name.startswith(f"{prefix}."):
                del sys.modules[module_name]
