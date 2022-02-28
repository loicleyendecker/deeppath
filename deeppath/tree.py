"""Define protocol"""

from typing import (
    Generic,
    Iterator,
    Protocol,
    TypeVar,
    Union,
    runtime_checkable,
)


K = TypeVar("K", contravariant=True)
V = TypeVar("V")


@runtime_checkable
class Tree(Protocol, Generic[K, V]):
    """Represent a tree-like structure"""

    def __getitem__(self, item: K) -> Union[V, "Tree[K, V]"]:
        ...

    def __len__(self) -> int:
        ...

    def __iter__(self) -> Iterator[str]:
        ...

    def __contains__(self, value: Union[V, "Tree[K, V]"]) -> bool:
        ...

    def __reversed__(self) -> Iterator[str]:
        ...


@runtime_checkable
class MutableTree(Protocol, Generic[K, V]):
    """Represent a tree-like structure"""

    def __getitem__(self, item: K) -> Union[V, Tree[K, V]]:
        ...

    def __setitem__(self, item: K, value: Union[V, "MutableTree[K, V]"]) -> None:
        ...

    def __len__(self) -> int:
        ...

    def __iter__(self) -> Union[Iterator[str], Iterator[V], Iterator["MutableTree[K, V]"]]:
        ...

    def __contains__(self, value: Union[V, Tree[K, V]]) -> bool:
        ...

    def __reversed__(self) -> Iterator[str]:
        ...
