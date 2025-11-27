"""Data structure conversion utilities."""

from collections import deque


def list_to_dict[F, K](
    input_list: list[dict[F, K]],
    key_for_key: F,
) -> dict[K, dict[F, K]]:
    """Convert list of dicts to dict of dicts keyed by specified field."""
    new_dict: dict[K, dict[F, K]] = {}
    for item in input_list:
        if key_for_key in item:
            key = item[key_for_key]
            new_dict[key] = item
    return new_dict


def slice_deque[T](original: deque[T], size: int, front: bool = False) -> list[T]:
    """Efficiently slices a `deque` from the specified size."""
    if front:
        # Slice from the front
        sliced: list[T] = []
        for current_index, each in enumerate(original):
            if current_index >= size:
                break
            sliced.append(each)
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
