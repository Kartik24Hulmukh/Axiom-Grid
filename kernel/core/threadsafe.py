"""Deterministic class-level synchronization helpers.

Production concurrency policy for Axiom-Grid (launch: 2026-09-16):

* Shared mutable services (provenance graph, SQLite memory store) are made
  thread-safe at the **class** level, at import time, with an explicit
  exclusion list.  This is deterministic and introspectable, unlike
  per-instance monkey patching (which breaks pickling, ``super()`` and
  subclassing, and silently evaluates properties during ``__init__``).
* Because the services are individually safe, the HTTP layer no longer needs a
  global serialization lock and can run pipelines concurrently.
"""

from __future__ import annotations

import functools
import inspect
from collections.abc import Iterable
from typing import Any, TypeVar

__all__ = ["synchronized", "synchronized_class"]

T = TypeVar("T", bound=type)


def synchronized(func: Any, lock_attr: str = "_lock") -> Any:
    """Wrap ``func`` so it runs while holding ``self.<lock_attr>`` (an RLock)."""

    @functools.wraps(func)
    def _locked(self: Any, *args: Any, **kwargs: Any) -> Any:
        lock = getattr(self, lock_attr, None)
        if lock is None:  # lock not installed yet (e.g. during __init__)
            return func(self, *args, **kwargs)
        with lock:
            return func(self, *args, **kwargs)

    _locked.__axiom_synchronized__ = True  # type: ignore[attr-defined]
    return _locked


def synchronized_class(
    exclude: Iterable[str] = (),
    lock_attr: str = "_lock",
) -> Any:
    """Class decorator: wrap every public instance method with the RLock.

    Dunder methods, private helpers (leading underscore), properties,
    ``staticmethod``/``classmethod`` objects, coroutines and anything named in
    ``exclude`` are left untouched.
    """

    skip = set(exclude)

    def _decorate(cls: T) -> T:
        for name, attr in list(vars(cls).items()):
            if name.startswith("_") or name in skip:
                continue
            if isinstance(attr, property):
                # Property getters read shared state too (e.g. SQL COUNT(*)).
                if attr.fget is not None and not getattr(
                    attr.fget, "__axiom_synchronized__", False
                ):
                    setattr(
                        cls,
                        name,
                        property(
                            synchronized(attr.fget, lock_attr),
                            attr.fset,
                            attr.fdel,
                            attr.__doc__,
                        ),
                    )
                continue
            if isinstance(attr, (staticmethod, classmethod)):
                continue
            if not inspect.isfunction(attr):
                continue
            if inspect.iscoroutinefunction(attr):
                continue
            if getattr(attr, "__axiom_synchronized__", False):
                continue
            setattr(cls, name, synchronized(attr, lock_attr))
        cls.__axiom_thread_safe__ = True  # type: ignore[attr-defined]
        return cls

    return _decorate
