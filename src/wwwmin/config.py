from dataclasses import dataclass, field
from pydantic import TypeAdapter
from functools import cached_property
import tomllib
from pathlib import Path
from typing import Any, Callable
import toml


@dataclass
class Config:
    path: Path
    section_classes: dict[str, type] = field(default_factory=dict)
    section_instances: dict[str, Any] = field(default_factory=dict)
    _data: dict | None = None

    @cached_property
    def data(self) -> dict:
        if self._data is None:
            self.read()
            assert self._data is not None
        return self._data

    def read(self):
        if not self.path.exists():
            self._data = {}
            return
        with self.path.open("rb") as fp:
            self._data = tomllib.load(fp)

    def parse(self, section_class: type, data: dict):
        return TypeAdapter(section_class).validate_python(data)

    def to_toml(self) -> str:
        return toml.dumps(
            {
                key: TypeAdapter(section_class).dump_python(self.section_instances[key])
                for key, section_class in self.section_classes.items()
            }
        )

    def section(self, key: str) -> Callable:
        def inner(cls: type):
            self.section_classes[key] = cls
            inst = self.parse(dataclass(cls), self.data.get(key, {}))
            self.section_instances[key] = inst
            return inst

        return inner


config = Config(Path.cwd() / "wwwmin.toml")
