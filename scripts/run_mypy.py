"""Run typechecking for all Python files."""

import argparse
import functools
import logging
import os
import pathlib
import subprocess
import sys
from collections.abc import Sequence

# By default, run mypy from the root of the repository.
REPO_ROOT = pathlib.Path(__file__).parent.parent
DEFAULT_PATHS = [REPO_ROOT]


def run_mypy(paths: list[pathlib.Path], dryrun: bool = False) -> int:
    """Run `mypy` to typecheck the given files or directories.

    Args:
        paths: Files or directories to type-check.

    Returns:
        0 if there were no errors, otherwise a non-zero error code.
    """
    command_args = ["mypy", *map(str, paths)]
    command = subprocess.list2cmdline(command_args)
    logging.info("Typechecking using command: %s", command)
    if dryrun:
        exit_code = 0
    else:
        completed_process = subprocess.run(command_args)
        exit_code = completed_process.returncode
    return exit_code


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--paths",
        "-p",
        type=pathlib.Path,
        default=DEFAULT_PATHS,
        nargs="*",
        help="Files or directories to typecheck.",
    )
    parser.add_argument(
        "--dryrun",
        action="store_true",
        help="Whether to actually run mypy or just log the command.",
    )
    args = parser.parse_args(argv)
    return args


def main(args: argparse.Namespace) -> int:
    logging.basicConfig(level=logging.INFO, force=True)
    logging.info("Typechecking...")
    exit_code = run_mypy(args.paths, args.dryrun)
    return exit_code


if __name__ == "__main__":
    sys.exit(main(parse_args(sys.argv[1:])))
