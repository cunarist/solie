from typing import Iterable, TypeVar

F = TypeVar("F")
K = TypeVar("K")
V = TypeVar("V")


def list_to_dict(input_list: list[dict[F, K]], key_for_key: F) -> dict[K, dict[F, K]]:
    new_dict = {}
    for item in input_list:
        if key_for_key in item:
            key = item[key_for_key]
            new_dict[key] = item
    return new_dict


def value_to_indexes(iterable: Iterable[V], target_value: V) -> list[int]:
    indexes: list[int] = []
    for item_index, item_value in enumerate(iterable):
        if item_value == target_value:
            indexes.append(item_index)
    return indexes
