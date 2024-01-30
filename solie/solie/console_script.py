import os
import subprocess
import sys


def start():
    python_interpreter = sys.executable
    env_variables = os.environ.copy()
    previous_pythonpath = env_variables.get("PYTHONPATH", "")
    new_pythonpath = os.path.dirname(python_interpreter)
    env_variables["PYTHONPATH"] = f"{previous_pythonpath}:{new_pythonpath}"
    if os.name == "nt":
        python_interpreter = os.path.join(
            os.path.dirname(python_interpreter),
            "pythonw.exe",
        )
        command = [python_interpreter, "-m", "solie"]
        subprocess.Popen(
            command,
            creationflags=subprocess.DETACHED_PROCESS,
            env=env_variables,
        )
    else:
        command = [python_interpreter, "-m", "solie"]
        subprocess.Popen(
            command,
            start_new_session=True,
            env=env_variables,
        )
