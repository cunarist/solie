from module import thread_toss


def do(signal, target_function):
    def job(*args):
        thread_toss.apply_async(target_function, *args)

    signal.connect(job)
