from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Any, Callable, Mapping

from pydantic import TypeAdapter
import appdirs
import toml


@dataclass
class Config:
    path: Path
    section_classes: dict[str, type] = field(default_factory=dict)
    section_instances: dict[str, Any] = field(default_factory=dict)
    _data: Mapping | None = None

    @cached_property
    def data(self) -> Mapping:
        if self._data is None:
            self.read()
            assert self._data is not None
        return self._data

    def read(self):
        match self.path:
            case Path() as path:
                self._data = self.read_file(path)
            case _:
                self._data = {}

    def read_file(self, path: Path) -> dict:
        if not path.exists():
            return {}
        with path.open("r") as fp:
            return toml.load(fp)

    def parse(self, section_class: type, data: dict):
        return TypeAdapter(section_class).validate_python(data)

    def dump_python(self) -> dict:
        return {
            key: TypeAdapter(section_class).dump_python(
                self.section_instances[key], mode="json"
            )
            for key, section_class in self.section_classes.items()
        }

    def dumps(self) -> str:
        return toml.dumps(self.dump_python())

    def dump(self) -> None:
        with self.path.open("w") as fp:
            fp.write(self.dumps())

    def section(self, key: str) -> Callable:
        def inner(cls: type):
            self.section_classes[key] = cls
            inst = self.parse(dataclass(cls), self.data.get(key, {}))
            self.section_instances[key] = inst
            return inst

        return inner


config = Config(Path(appdirs.user_config_dir("wwwmin")) / "config.toml")
