def do(level, increase_ratio):
    if level == 0:
        return 0
    else:
        return ((increase_ratio**level) - 1) / (increase_ratio - 1)
