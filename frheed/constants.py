"""
Constants and settings for use elsewhere.
"""
import os
from appdirs import user_config_dir, user_log_dir
from typing import Optional
from dataclasses import dataclass

DATA_DIR = os.path.normpath(os.path.expanduser("~/FRHEED"))
os.makedirs(DATA_DIR, exist_ok=True)

CONFIG_DIR = os.path.join(user_config_dir(), "FRHEED", "")
os.makedirs(CONFIG_DIR, exist_ok=True)

LOG_DIR = os.path.join(user_log_dir(), "FRHEED", "")
os.makedirs(LOG_DIR, exist_ok=True)

_LOCAL_DIR = os.path.dirname(__file__)
RESOURCE_DIR = os.path.normpath(os.path.join(_LOCAL_DIR, "resources", ""))
ICONS_DIR = os.path.normpath(os.path.join(RESOURCE_DIR, "icons", ""))
os.makedirs(ICONS_DIR, exist_ok=True)

WINDOW_ICON_PATH = os.path.join(ICONS_DIR, "FRHEED.ico")

# Colors from matplotlib tableau colors
# Used matplotlib.colors.to_hex(...) for each color
# https://matplotlib.org/3.1.0/gallery/color/named_colors.html
COLOR_DICT = {
    "blue": "#1f77b4",
    "orange": "#ff7f0e",
    "green": "#2ca02c",
    "red": "#d62728",
    "purple": "#9467bd",
    "brown": "#8c564b",
    "pink": "#e377c2",
    "gray": "#7f7f7f",
    "olive": "#bcbd22",
    "cyan": "#17becf",
}


def get_data_dir(user: Optional[str] = None, experiment: Optional[str] = None) -> str:
    """Create a data directory based on the given user and experiment name.

    Args:
        user (Optional[str], optional): The name of the current user.
            If the default of None is used, no user subfolder will be created.
        experiment (Optional[str], optional): The name of the current experiment.
            If the default of None is used, no experiment subfolder will be created.

    Returns:
        str: Path to the generated data directory.
    """

    # Base data directory for FRHEED
    data_dir = DATA_DIR

    # Create subfolder for user
    if user is not None:
        data_dir = os.path.join(data_dir, user, "")

    # Create subfolder for experiment
    if experiment is not None:
        data_dir = os.path.join(data_dir, experiment, "")

    # Make sure directories exist
    os.makedirs(data_dir, exist_ok=True)

    return data_dir


if __name__ == "__main__":

    def test():
        print(f"Data directory: {DATA_DIR}")
        print(f"Config directory: {CONFIG_DIR}")
        print(f"Resource directory: {RESOURCE_DIR}")
        print(f"Icons directory: {ICONS_DIR}")
        print(f"Test directory: {get_data_dir('test', 'test')}")

    test()
