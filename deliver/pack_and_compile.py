import os
import subprocess
import shutil
import pathlib
from setuptools import setup

from Cython.Build import cythonize

userpath = str(pathlib.Path.home())
condapath = userpath + "/miniconda3/condabin/conda.bat"

commands = [
    f"{condapath} activate solsol",
    "pyinstaller pack.spec --noconfirm",
]
subprocess.run("&&".join(commands))

# https://medium.com/@xpl/protecting-python-sources-using-cython-dcd940bb188e
# https://stackoverflow.com/questions/66967488/creating-pyd-files-in-folder-and-subfolder-using-python

finalpath = os.getcwd() + "/dist/Solsol"

excludes = ("__init__.py",)
os.chdir(finalpath + "/module")
for location, foldernames, filenames in os.walk(finalpath + "/module"):
    for filename in filenames:
        if filename.lower().endswith(".py") and filename not in excludes:
            setup(
                ext_modules=cythonize(location + "/" + filename, language_level=3),
                script_args=["build_ext"],
                options={"build_ext": {"inplace": True}},
            )
            pure_name, extension = os.path.splitext(filename)
            os.remove(os.path.join(location, filename))
            os.remove(os.path.join(location, pure_name + ".c"))

includes = ("__pycache__", "build")
os.chdir(finalpath + "/module")
for location, foldernames, filenames in os.walk(finalpath + "/module"):
    for foldername in foldernames:
        if foldername in includes:
            fullpath = os.path.join(location, foldername)
            shutil.rmtree(fullpath, ignore_errors=True)

includes = (".blend", ".blend1", ".afphoto")
os.chdir(finalpath + "/resource")
for location, foldernames, filenames in os.walk(finalpath + "/resource"):
    for filename in filenames:
        for extension in includes:
            if filename.lower().endswith(extension):
                os.remove(os.path.join(location, filename))
