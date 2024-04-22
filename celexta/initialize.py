"""Module holding all the initialization code"""

import logging
import logging.config
import shutil
from pathlib import Path
from pprint import pformat

import yaml

from celexta import __CELEXTA_DIR__ as ROOT_DIR

log = logging.getLogger(__name__)

DIRS = {
    "ROOT": ROOT_DIR,
    "UI": ROOT_DIR / "ui",
    "DATA": ROOT_DIR / "data",
    "CONFIG": ROOT_DIR / "config",
}

DEFAULT_CONFIG_FNAME = Path("~/.celexta/config/default_config.yaml").expanduser().resolve()
USER_CONFIG_FNAME = Path("~/.celexta/config/user_config.yaml").expanduser().resolve()
FORMATTER = logging.Formatter(
    "%(asctime)s - %(levelname)8s - [%(filename)s:%(lineno)3s - %(funcName)10s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)


def update_logging(log_level: str | int, log_file: str | Path | None = None) -> None:
    """Update logging level and add file handler if provided.

    Parameters
    ----------
    log_level : str | int
        Logging level.
    log_file : Optional[str]
        Path to file where logs will be store. If ``None``, no logs
        will be written to file.
    """
    root = logging.getLogger()
    root.setLevel(log_level)

    if log_file:
        # Expand path and make sure path exists
        log_file = Path(log_file).expanduser().resolve()
        log_file.parent.mkdir(parents=True, exist_ok=True)
        f_hdlr = logging.FileHandler(
            filename=log_file,
            encoding="utf-8",
            mode="w",
        )
        f_hdlr.setFormatter(FORMATTER)
        root.addHandler(f_hdlr)


def load_config() -> dict:
    """Load the configuration file for Celexta into dictionary.

    Loads the default configuration first, found in
    ``'~/.celexta/config/default_config.yaml'``.
    Then updates that with anything found in
    ``'~/.celexta/config/user_config.yaml'``
    If it doesn't find the configuration, it copies it from the source code
    into the aforementioned paths.

    Returns
    -------
    dict
        Dictionay containing the configuration.

    """
    log.debug("Looking for config file")
    # if the default config file doesn't exist, it generally means it is the first
    # time celexta is installed on the computer, so copy the file
    if not DEFAULT_CONFIG_FNAME.exists():
        log.debug(f"No default configuration under '{DEFAULT_CONFIG_FNAME!s}', creating one")
        DEFAULT_CONFIG_FNAME.parent.mkdir(parents=True, exist_ok=True)
        # Copy the default config from celexta source code
        shutil.copyfile(DIRS["CONFIG"] / "default_config.yaml", DEFAULT_CONFIG_FNAME)

    # Load default config
    with open(DEFAULT_CONFIG_FNAME, encoding="utf-8") as f:
        config = yaml.safe_load(f)
        log.debug(f"Loaded default configuration from:\n{DEFAULT_CONFIG_FNAME}")

    # also check if the user_config exists otherwise copy the source user config
    if not USER_CONFIG_FNAME.exists():
        shutil.copyfile(DIRS["CONFIG"] / "user_config.yaml", USER_CONFIG_FNAME)
    # Load user config
    with open(USER_CONFIG_FNAME, encoding="utf-8") as f:
        user_config = yaml.safe_load(f)
        log.debug(f"Loaded user configuration from:\n{USER_CONFIG_FNAME}")

    # Update default config with user config
    for k, d in user_config.items():
        # Check that user didn't add invalid keys to yaml file
        if k not in config:
            err_msg = f"User configuration contains invalid keys, check file:\n{USER_CONFIG_FNAME}"
            raise ValueError(err_msg)
        config[k].update(d)

    log.debug(f"Config:\n{pformat(config)}")

    return config


def update_last_opened(path: str | Path) -> None:
    """Update the 'last_opened' key of the user configuration file"""
    # Get the path to the configuration file

    with open(USER_CONFIG_FNAME, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    config["filenames"]["last_opened"] = str(Path(path).expanduser().resolve())

    with open(USER_CONFIG_FNAME, "w", encoding="utf-8") as f:
        yaml.dump(config, stream=f)
        log.debug(f"Updated last opened file with:\n{path}")
