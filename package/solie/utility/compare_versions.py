def is_left_version_higher(version1: str, version2: str) -> bool:
    versions1 = [int(v) for v in version1.split(".")]
    versions2 = [int(v) for v in version2.split(".")]
    for turn in range(max(len(versions1), len(versions2))):
        v1 = versions1[turn] if turn < len(versions1) else 0
        v2 = versions2[turn] if turn < len(versions2) else 0
        if v1 > v2:
            return True
        elif v1 < v2:
            return False
    return False
