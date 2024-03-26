"""Utilities for common Poetry actions.

This script should only be called from the root of the repository
where the `pyproject.toml` is contained.
"""

# WARNING: This script should not contain external dependencies.
import argparse
import functools
import logging
import os
import pathlib
import subprocess
import sys
from collections.abc import Sequence

# Requirements files to export by Poetry groups
REQUIREMENTS_FILENAME_BY_POETRY_GROUPS: dict[tuple[str, ...], str] = {
    ("main",): "requirements.txt",
    ("main", "typechecking", "linting"): "requirements-dev.txt",
}

# Header for all requirements files
REQUIREMENTS_HEADER = """\
############################## WARNING ##############################
# THIS FILE IS GENERATED AUTOMATICALLY FROM THE POETRY LOCKFILE
#
# DO NOT EDIT MANUALLY
#
# TO UPDATE REQUIREMENTS, SEE `scripts/poetry_tools.py`
############################## WARNING ##############################
"""


def ensure_correct_cwd() -> None:
    """Raise a ValueError if the current working directory is incorrect."""
    cwd = pathlib.Path.cwd().resolve()
    if cwd.name != "FRHEED":
        raise ValueError("This script should only be run from the `FRHEED` directory")

    pyproject_file = cwd / "pyproject.toml"
    if not pyproject_file.exists():
        raise FileNotFoundError(f"{pyproject_file} does not exist")


@functools.cache
def get_poetry_binary_path() -> pathlib.Path:
    """Returns the path to the `poetry.exe` binary.

    Raises:
        FileNotFoundError if `poetry.exe` is not found in any of the typical locations.
    """
    home = pathlib.Path.home()

    # The %APPDATA% directory in Windows
    # https://stackoverflow.com/a/13184486/10342097
    appdata = pathlib.Path(os.getenv("APPDATA", ""))

    # Directories to look for the Poetry binary in
    # https://python-poetry.org/docs/#installation
    possible_dirs = [home / ".local" / "bin", appdata / "Python" / "Scripts"]  # Unix  # Windows
    for possible_dir in possible_dirs:
        poetry_binary_path = possible_dir / "poetry.exe"
        if poetry_binary_path.exists():
            logging.info("Poetry binary found at '%s'", poetry_binary_path)
            return poetry_binary_path

    # Poetry binary not found in any of the locations
    raise FileNotFoundError(
        f"`poetry.exe` not found in any of the typical locations: {possible_dirs}"
    )


def update_poetry_lock(verbose: bool = True, update_packages: bool = True) -> int:
    """Create the `poetry.lock` file in the repo root.

    Args:
        verbose: Whether to verbosely print what poetry is doing.
        update_packages: Whether to update locked package versions or just refresh the lock file.

    Returns:
        0 if the operation was successful, otherwise a non-zero error code.
    """
    maybe_verbose = ["-vvv"] if verbose else []
    maybe_update_packages = [] if update_packages else ["--no-update"]
    poetry_binary_path = get_poetry_binary_path()
    command_args = [str(poetry_binary_path), *maybe_verbose, "lock", *maybe_update_packages]
    command = subprocess.list2cmdline(command_args)
    logging.info("Updating `poetry.lock` using command: %s", command)
    completed_process = subprocess.run(command_args)
    return completed_process.returncode


def export_poetry_lock(
    groups: Sequence[str], output_file: pathlib.Path, verbose: bool = False
) -> int:
    """Export `poetry.lock` to a requirements file.

    Args:
        groups: The Poetry groups in `pyproject.toml` to export in addition to
            the implicit `main` group in `tool.poetry.dependencies`.
        output_file: The filepath to export the requirements to.

    Returns:
        0 if the requirements were exported successfully, otherwise a non-zero error code.
    """
    poetry_binary_path = get_poetry_binary_path()
    maybe_verbose = ["-vvv"] if verbose else []
    command_args = [
        str(poetry_binary_path),
        *maybe_verbose,
        "export",
        "--without-hashes",
        "--without-urls",
        "--with",
        ",".join(groups),
    ]
    command = subprocess.list2cmdline(command_args)
    logging.info("Exporting `poetry.lock` to requirements using command: %s", command)
    try:
        # Convert output bytes to text, strip leading/trailing blank space, and replace
        # double-newlines (\r\n) with single newlines (\n).
        requirements = subprocess.check_output(command_args).decode()
        requirements = requirements.strip().replace("\r\n", "\n")
        exit_code = 0
    except subprocess.CalledProcessError as cpe:
        logging.error("Error exporting `poetry.lock`: %s", cpe)
        exit_code = cpe.returncode

    # Update the requirements file if `poetry.lock` was exported successfully
    if exit_code == 0:
        # Add trailing newline since all files should end with one
        output_file.write_text(REQUIREMENTS_HEADER + requirements + "\n")
        logging.info("Exported requirements to '%s':\n%s", output_file, requirements)

    return exit_code


def get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Run commands with verbose output."
    )

    actions = parser.add_subparsers(dest="action")

    lock = actions.add_parser(
        "lock", help="Update `poetry.lock` using dependencies in `pyproject.toml`."
    )
    lock.add_argument(
        "--update",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Whether to update locked package versions or just refresh the lock file.",
    )

    export = actions.add_parser("export", help="Export `poetry.lock` to requirements.")
    export.add_argument(
        "--lock",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Update `poetry.lock` (but not installed packages) before exporting.",
    )
    return parser


def main(argv: Sequence[str] | None) -> int:
    logging.basicConfig(level=logging.INFO, force=True)
    ensure_correct_cwd()
    parser = get_parser()
    args = parser.parse_args(argv)
    verbose: bool = args.verbose
    if args.action == "lock":
        exit_code = update_poetry_lock(verbose, args.update)
    elif args.action == "export":
        if args.lock:
            exit_code = update_poetry_lock(verbose, update_packages=False)

        for groups, output_filename in REQUIREMENTS_FILENAME_BY_POETRY_GROUPS.items():
            output_filepath = pathlib.Path(output_filename).resolve()
            exit_code += export_poetry_lock(groups, output_filepath, verbose=verbose)
    else:
        logging.info("Unknown action '%s'", args.action)
        parser.print_help()
        exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
