from collections import deque
from typing import TypeVar

F = TypeVar("F")
K = TypeVar("K")
V = TypeVar("V")
T = TypeVar("T")


def list_to_dict(input_list: list[dict[F, K]], key_for_key: F) -> dict[K, dict[F, K]]:
    new_dict: dict[K, dict[F, K]] = {}
    for item in input_list:
        if key_for_key in item:
            key = item[key_for_key]
            new_dict[key] = item
    return new_dict


def slice_deque(original: deque[T], size: int, front: bool = False) -> list[T]:
    """
    Efficiently slices a `deque` from the specified size.
    """
    if front:
        # Slice from the beginning
        sliced: list[T] = []
        current_index = 0
        for each in original:
            if current_index >= size:
                break
            sliced.append(each)
            current_index += 1
    else:
        # Slice from the end
        sliced: list[T] = []
        current_index = 0
        for each in reversed(original):
            if current_index >= size:
                break
            sliced.append(each)
            current_index += 1
        sliced.reverse()

    return sliced
