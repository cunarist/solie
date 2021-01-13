from recipe import thread


def do(signal, target_function):
    def job(*args):
        thread.apply_async(target_function, *args)

    signal.connect(job)
