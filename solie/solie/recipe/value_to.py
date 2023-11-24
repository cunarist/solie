def keys(dictionary_object, target_value):
    keys = []
    for item_key, item_value in dictionary_object.items():
        if item_value == target_value:
            keys.append(item_key)
    return keys


def indexes(iterable, target_value):
    indexes = []
    for item_index, item_value in enumerate(iterable):
        if item_value == target_value:
            indexes.append(item_index)
    return indexes
