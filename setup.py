# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

with open("requirements.txt", "r", encoding="utf8") as fi:
    install_requires = fi.read().split("\n")
    
setup(
      name = "FRHEED",
      version = "3.0.0",
      description = "An open-source RHEED GUI.",
      author = "Elliot Young",
      author_email = "elliotyoung@frheed.com",
      url = "https://github.com/ecyoung3/FRHEED",
      packages = find_packages(),
      include_package_data = True,
      # long_description = long_description, # TODO
      long_description_content_type = "text/markdown",
      exclude_package_data = {
          "": [".gitignore"],
          },
      setup_requires = [
          "setuptools-git"
          ],
      install_requires = install_requires,
      classifiers = [
        "Programming Language :: Python :: 3.9.5",
        ]
      )

# if __name__ == "__main__":
#     import subprocess
#     import sys
#     from pathlib import Path
    
#     filename = str(Path(__file__).name)
#     print(subprocess.check_output([sys.executable, filename]))
