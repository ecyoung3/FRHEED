#!/usr/bin/env python
"""Create a virtual environment."""

import argparse
import logging
import pathlib
import subprocess
import sys
from collections.abc import Sequence

DEFAULT_VENV_DIR = pathlib.Path.home() / ".virtualenvs"


def create_venv(venv_path: pathlib.Path, python: str, dryrun: bool = False) -> int:
    """Create a virtual environment at the given path.

    Args:
        venv_path: Where to create the virtual environment.
        python: Python interpreter name or executable path for the virtual environment.
        dryrun: Whether to actually create the virtual environment or just log the command.

    Returns:
        0 if the operation succeeded (or dryrun=True), otherwise an error code.
    """
    logging.info(
        "Creating virtual environment '%s' with Python interpreter '%s' in '%s'",
        venv_path.name,
        python,
        venv_path.parent,
    )
    command_args = ["virtualenv", "-p", str(python), str(venv_path)]
    if dryrun:
        command = subprocess.list2cmdline(command_args)
        logging.info("Virtual environment would be created using command: %s", command)
        exit_code = 0
    else:
        try:
            exit_code = subprocess.check_call(command_args)
            logging.info("Successfully created virtual environment")
            add_frheed_pth(venv_path)
        except subprocess.CalledProcessError as cpe:
            exit_code = cpe.returncode
            logging.error("Failed to create virtual environment")

    return exit_code


def add_frheed_pth(venv_path: pathlib.Path) -> pathlib.Path:
    """Add the FRHEED repo root path to a `frheed.pth` file in a virtual environment.

    This allows the `frheed` code to be run from within the virtual environment.

    Args:
        venv_path: Path to the virtual environment root.

    Returns:
        The path to the created `frheed.pth` file.
    """
    frheed_root = pathlib.Path(__file__).parent.parent
    insert_frheed_path = f"import sys; sys.path.insert(0, r'{frheed_root}')"
    pth_file = venv_path / "frheed.pth"
    pth_file.write_text(insert_frheed_path)
    logging.info("Wrote to '%s': '%s'", pth_file, insert_frheed_path)
    return pth_file


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", type=pathlib.Path, help="Virtual environment name.")
    parser.add_argument(
        "--dir",
        "-d",
        type=pathlib.Path,
        default=DEFAULT_VENV_DIR,
        help="Parent directory to create the virtual environment in.",
    )
    parser.add_argument(
        "--python",
        "-p",
        default=sys.executable,
        help="Python interpreter name or executable path for the virtual environment.",
    )
    parser.add_argument(
        "--dryrun",
        action="store_true",
        help="Whether to actually create the virtual environment or just log the command.",
    )
    args = parser.parse_args(argv)
    return args


def main(args: argparse.Namespace) -> int:
    logging.basicConfig(level=logging.INFO, force=True)
    path: pathlib.Path = args.dir / args.name
    create_venv(path, args.python, args.dryrun)
    return 0


if __name__ == "__main__":
    sys.exit(main(parse_args(sys.argv[1:])))
