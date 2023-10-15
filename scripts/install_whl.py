#!/usr/bin/env python
"""Install a Python module from a .whl file."""

import argparse
import importlib
import logging
import pathlib
import subprocess
import sys
import warnings

from collections.abc import Sequence


def import_module_without_warnings(module_name: str) -> importlib.ModuleType:
    """Return a module imported with warnings suppressed."""
    # Suppress warnings when importing the module, e.g. PySpin KMP_AFFINITY warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        module = importlib.import_module(module_name)
    return module


def install_whl(
    whl_path: pathlib.Path, module_name: str, reinstall: bool = True, dryrun: bool = False
) -> int:
    """Install a Python module from a .whl file.

    Args:
        whl_path: Path to the .whl file to install.
        module_name: Name of the module to be installed.
        reinstall: Whether to install the .whl even if the module is already installed.
        dryrun: Whether to actually install the .whl or just log the command.

    Returns:
        0 if installation succeeded (or dryrun=True), otherwise an error code.

    Raises:
        ImportError if the .whl was successfully installed but the module cannot be imported.
    """
    try:
        import_module_without_warnings(module_name)
        if not reinstall:
            logging.info(
                "Module '%s' is already installed and reinstall=False; aborting installation",
                module_name,
            )
            return 0
    except ImportError:
        logging.info(
            "Module '%s' is not installed; attempting to install from '%s'", module_name, whl_path
        )

    command_args = [sys.executable, "-m", "pip", "install", str(whl_path), "--force-reinstall"]
    if dryrun:
        command = subprocess.list2cmdline(command_args)
        exit_code = 0
        logging.info(".whl would be installed using command: %s", command)
    else:
        try:
            exit_code = subprocess.check_call(command_args)
        except subprocess.CalledProcessError as cpe:
            exit_code = cpe.returncode

    # If .whl installation succeeded, check that the module is now importable
    if exit_code == 0:
        # Invalidate the import cache so importlib can find the module if it was newly installed
        # https://docs.python.org/3/library/importlib.html#importlib.import_module
        importlib.invalidate_caches()

        try:
            import_module_without_warnings(module_name)
        except ImportError:
            logging.error(
                "Installed '%s' but module '%s' still cannot be imported", whl_path, module_name
            )
            raise

    return exit_code


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=pathlib.Path, help="Path to the .whl file to install.")
    parser.add_argument("module", help="Name of the module to be installed.")
    parser.add_argument(
        "--reinstall",
        "-r",
        action="store_true",
        help="Whether to install the .whl even if the module is already installed.",
    )
    parser.add_argument(
        "--dryrun",
        "-d",
        action="store_true",
        help="Whether to actually install the .whl or just log the command.",
    )
    args = parser.parse_args(argv)
    return args


def main(args: argparse.Namespace) -> int:
    logging.basicConfig(level=logging.INFO, force=True)
    exit_code = install_whl(args.path, args.module, args.reinstall, args.dryrun)
    return exit_code


if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    sys.exit(main(args))
