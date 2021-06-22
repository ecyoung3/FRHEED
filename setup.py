# -*- coding: utf-8 -*-

from setuptools import setup, find_packages, Command
import sys
import os
from shutil import rmtree
from pathlib import Path

# Package metadata
NAME = "frheed"
DESCRIPTION = "An open source GUI for real-time RHEED analysis."
AUTHOR = "Elliot Young"
AUTHOR_EMAIL = "elliotyoung@frheed.com"
VERSION = "0.0.1"
URL = "https://github.com/ecyoung3/FRHEED"
PYTHON_REQUIRES = "==3.8.10"  # TODO: Find minimum working verssion

# Load requirements
here = os.path.abspath(os.path.dirname(__file__))
requirements_file = os.path.join(here, "requirements.txt")
INSTALL_REQUIRES = Path(requirements_file).read_text().split("\n")

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
    """ Support setup.py uploading to PyPI. """
    
    description = "Build and publish the package to PyPI"
    user_options = []
    
    @staticmethod
    def status(s):
        """ Print status in bold. """
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
      name = NAME,
      version = about["__version__"],
      description = DESCRIPTION,
      author = AUTHOR,
      author_email = AUTHOR_EMAIL,
      url = URL,
      packages = find_packages(),
      include_package_data = True,
      # long_description = long_description,  # TODO
      long_description_content_type = "text/markdown",
      exclude_package_data = {
          "": [".gitignore"],
          },
      setup_requires = [
          "setuptools-git"
          ],
      install_requires = INSTALL_REQUIRES,
      classifiers = [
        "Programming Language :: Python :: 3.8",
        ],
      cmdclass = {
          "upload": UploadCommand
          },
      )