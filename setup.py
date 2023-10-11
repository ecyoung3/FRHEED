# -*- coding: utf-8 -*-

from setuptools import setup, find_packages, Command
import sys
import os
from shutil import rmtree
from pathlib import Path

# Package metadata
NAME = "frheed"
DESCRIPTION = "FRHEED is a GUI for real-time Reflection High-Energy Electron Diffraction (RHEED) analysis."
AUTHOR = "Elliot Young"
AUTHOR_EMAIL = "elliot.young1996@gmail.com"
VERSION = "0.0.2"  # Must not match existing PyPI version or upload will fail
URL = "https://github.com/ecyoung3/FRHEED"
PYTHON_REQUIRES = "==3.8.10"  # Spinnaker requires Python 3.8

# Load requirements
here = os.path.abspath(os.path.dirname(__file__))
requirements_file = os.path.join(here, "requirements.txt")
INSTALL_REQUIRES = Path(requirements_file).read_text().split("\n")

# Load long description using regular description as fallback.
try:
    readme_file = os.path.join(here, "README.md")
    LONG_DESCRIPTION = Path(readme_file).read_text()
except:
    LONG_DESCRIPTION = DESCRIPTION

# Load version info from __version__.py
about = {}
if not VERSION:
    project_slug = NAME.lower().replace("-", "_").replace(" ", "_")
    with open(os.path.join(here, project_slug, "__version__.py")) as f:
        exec(f.read(), about)
else:
    about["__version__"] = VERSION


# https://github.com/kennethreitz/setup.py/blob/master/setup.py
class UploadCommand(Command):
    """
    Support setup.py uploading to PyPI.
    To use, run `python setup.py upload` in the command prompt
    from the directory that this file is in.
    """

    description = "Build and publish the package to PyPI."
    user_options = []

    @staticmethod
    def status(s):
        """Print status in bold."""
        print(f"\033[1m{s}\033[0m")

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        try:
            self.status("Removing previous builds...")
            rmtree(os.path.join(here, "dist"))
        except OSError:
            pass

        self.status("Updating requirements.txt")
        from frheed.utils import gen_reqs

        gen_reqs()

        self.status("Building source and wheel (universal) distribution...")
        os.system(f"{sys.executable} setup.py sdist bdist_wheel --universal")

        self.status("Uploading the package to PyPI via Twine...")
        os.system("twine upload dist/*")

        self.status("Pushing git tags...")
        os.system(f"git tag v{VERSION}")
        os.system("git push --tags")

        sys.exit()


setup(
    name=NAME,
    version=about["__version__"],
    description=DESCRIPTION,
    author=AUTHOR,
    author_email=AUTHOR_EMAIL,
    url=URL,
    packages=find_packages(),
    include_package_data=True,
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/markdown",
    exclude_package_data={
        "": [".gitignore"],
    },
    setup_requires=["setuptools-git"],
    install_requires=INSTALL_REQUIRES,
    classifiers=[
        "Programming Language :: Python :: 3.8",
    ],
    cmdclass={"upload": UploadCommand},
)
