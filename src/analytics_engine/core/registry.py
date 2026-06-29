"""Generic registry pattern for metrics, detectors, and other extensible components."""

from __future__ import annotations

from typing import Generic, TypeVar

T = TypeVar("T")


class Registry(Generic[T]):
    """A registry that maps string codes to instances.

    Components self-register via the `register` class method decorator.
    Vertical configs enable/disable components by code.
    """

    def __init__(self, name: str):
        self._name = name
        self._items: dict[str, T] = {}

    def register(self, cls: type) -> type:
        instance = cls()
        code = getattr(instance, "code", None)
        if code is None:
            raise ValueError(f"{cls.__name__} must have a 'code' attribute to register in {self._name}")
        if code in self._items:
            raise ValueError(f"Duplicate {self._name} code: {code!r}")
        self._items[code] = instance
        return cls

    def get(self, code: str) -> T | None:
        return self._items.get(code)

    def get_enabled(self, enabled_codes: list[str]) -> list[T]:
        return [self._items[code] for code in enabled_codes if code in self._items]

    def all_codes(self) -> list[str]:
        return list(self._items.keys())

    def __len__(self) -> int:
        return len(self._items)
