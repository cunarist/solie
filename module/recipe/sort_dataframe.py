def do(df):
    df = df.sort_index(axis="index")
    df = df.sort_index(axis="columns")
    return df
