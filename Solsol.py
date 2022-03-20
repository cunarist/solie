import os
import sys
import platform
from urllib import request
import tempfile
import subprocess
import shutil
import tkinter as tk
import threading
import time
import pathlib

userpath = str(pathlib.Path.home())
condapath = userpath+"/miniconda3/condabin/conda.bat"

# ■■■■■ check runtime environment ■■■■■

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    # running in a PyInstaller bundle
    is_development_mode = False
else:
    # running in the project folder
    is_development_mode = True

# ■■■■■ show splash screen ■■■■■

display_event = threading.Event()


def job():
    global balloon
    splash_window = tk.Tk()
    splash_window.overrideredirect(1)
    splash_window.attributes("-transparentcolor", "gray", "-topmost", True)
    balloon_image = tk.PhotoImage(file="./resource/balloon_1.png")
    balloon = tk.Label(splash_window, bg="gray", image=balloon_image)
    balloon.pack()
    splash_window.eval("tk::PlaceWindow . Center")
    display_event.set()
    splash_window.mainloop()


threading.Thread(target=job, daemon=True).start()
display_event.wait()

# ■■■■■ detect if conda is intalled ■■■■■

if not os.path.isdir(f"{userpath}/miniconda3"):
    balloon_image = tk.PhotoImage(file="./resource/balloon_2.png")
    balloon.configure(image=balloon_image)

    if platform.system() == "Windows":
        url = "https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe"
        installer_file = request.urlopen(url).read()

        with tempfile.TemporaryDirectory() as directory:
            with open(directory + "/installer.exe", mode="wb") as file:
                filepath = file.name
                file.write(installer_file)

            # conda is installed for 'AllUsers' with administrator privileges by default
            commands = [
                f"{filepath} /S /InstallationType=JustMe",
            ]
            subprocess.run(
                "&&".join(commands),
                creationflags=subprocess.CREATE_NO_WINDOW,
                shell=True,
            )

    elif platform.system() == "Linux":
        sys.exit()

    elif platform.system() == "Darwin":  # macOS
        sys.exit()

# ■■■■■ prepare python environment ■■■■■

if not os.path.isdir("./habitat"):
    commands = [
        f"{condapath} create --prefix ./habitat --no-default-packages --yes",
    ]
    run_output = subprocess.run(
        "&&".join(commands),
        creationflags=subprocess.CREATE_NO_WINDOW,
    )

commands = [
    f"{condapath} compare ./resource/environment.yaml --prefix ./habitat",
]
run_output = subprocess.run(
    "&&".join(commands),
    creationflags=subprocess.CREATE_NO_WINDOW,
    shell=True,
)

if run_output.returncode != 0:
    # when environment doesn't satisfy the configuration file

    balloon_image = tk.PhotoImage(file="./resource/balloon_3.png")
    balloon.configure(image=balloon_image)

    if is_development_mode:
        # install execution packages and development packages
        commands = [
            f"{condapath} env update --file ./resource/environment.yaml --prefix"
            " ./habitat",
            f"{condapath} activate ./habitat",
            "pip install pyinstaller",
            "pip install cython",
            "pip install pyside6",
            "pip install flake8",
            "pip install pep8-naming",
            "pip install flake8-variables-names",
            "pip install flake8-print",
            "pip install flake8-blind-except",
            "pip install flake8-comprehensions",
            "pip install flake8-use-fstring",
            "pip install pygount",
        ]
    else:
        # install only execution packages and prune up
        commands = [
            f"{condapath} env update --file ./resource/environment.yaml --prune"
            " --prefix ./habitat",
        ]
    subprocess.run(
        "&&".join(commands),
        creationflags=subprocess.CREATE_NO_WINDOW,
        shell=True,
    )

# ■■■■■ code editor settings file ■■■■■

if is_development_mode:
    if not os.path.isfile("./.vscode/settings.json"):
        os.makedirs("./.vscode", exist_ok=True)
        shutil.copy("./resource/vscode_settings.json", "./.vscode")
        os.rename("./.vscode/vscode_settings.json", "./.vscode/settings.json")

# ■■■■■ run the real app ■■■■■

# with administrator priviliges on other process

balloon_image = tk.PhotoImage(file="./resource/balloon_4.png")
balloon.configure(image=balloon_image)

if platform.system() == "Windows":
    current_directory = os.getcwd()
    commands = [
        f"{condapath} activate ./habitat",
        "start pythonw ./module/entry.py",
    ]
    subprocess.run(
        "&&".join(commands),
        creationflags=subprocess.CREATE_NO_WINDOW,
        shell=True,
    )


elif platform.system() == "Linux":
    sys.exit()

elif platform.system() == "Darwin":  # macOS
    sys.exit()

# ■■■■■ show splash screen a bit more ■■■■■

time.sleep(3)
