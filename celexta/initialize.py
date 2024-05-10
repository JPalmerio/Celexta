"""Contains all the initialization code"""

import logging
import logging.config
import shutil
import sys
from pathlib import Path
from pprint import pformat

import yaml

from celexta import __CELEXTA_DIR__ as CELEXTA_DIR
from celexta import __CELEXTA_SRC_DIR__ as SRC_DIR

log = logging.getLogger(__name__)
SRC_DIRS = {
    "ROOT": SRC_DIR,
    "UI": SRC_DIR / "ui",
    "DATA": SRC_DIR / "data",
    "CONFIG": SRC_DIR / "config",
}
USR_DIRS = {
    "ROOT": CELEXTA_DIR,
    "GCN_MAKER": CELEXTA_DIR / "gcn_maker",
    "CONFIG": CELEXTA_DIR / "config",
}

FORMATTER = logging.Formatter(
    "%(asctime)s - %(levelname)8s - %(name)s - [%(filename)s:%(lineno)3s - %(funcName)10s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def default_logging():
    """Create default logging configuration"""
    log = logging.getLogger()
    s_hdlr = logging.StreamHandler(stream=sys.stdout)
    s_hdlr.setFormatter(FORMATTER)
    log.addHandler(s_hdlr)
    log.setLevel(logging.DEBUG)
    return log


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
    # Raise level of certain packages that flood logging
    for name in ("matplotlib", "PyQt6.uic"):
        logging.getLogger(name).setLevel(logging.WARNING)

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
        Dictionary containing the configuration.

    """
    log.debug("Looking for config file")
    if not USR_DIRS["ROOT"].exists():
        log.info(f"Celexta directory not found, creating one under '{USR_DIRS['ROOT']}'")
        USR_DIRS["ROOT"].mkdir(exist_ok=False, parents=True)

    # if the default config file doesn't exist, it generally means it is the first
    # time celexta is installed on the computer, so copy the file
    default_config_fname = USR_DIRS["CONFIG"] / "default_config.yaml"
    if not default_config_fname.exists():
        log.debug(f"No default configuration under '{default_config_fname!s}', creating one")
        default_config_fname.parent.mkdir(parents=True, exist_ok=True)
        # Copy the default config from celexta source code
        shutil.copyfile(SRC_DIRS["CONFIG"] / "default_config.yaml", default_config_fname)

    # Load default config
    with open(default_config_fname, encoding="utf-8") as f:
        config = yaml.safe_load(f)
        log.debug(f"Loaded default configuration from:\n{default_config_fname}")

    # also check if the user_config exists otherwise copy the source user config
    user_config_fname = USR_DIRS["CONFIG"] / "user_config.yaml"
    if not user_config_fname.exists():
        shutil.copyfile(SRC_DIRS["CONFIG"] / "user_config.yaml", user_config_fname)
    # Load user config
    with open(user_config_fname, encoding="utf-8") as f:
        user_config = yaml.safe_load(f)
        log.debug(f"Loaded user configuration from:\n{user_config_fname}")

    # Update default config with user config
    for k, d in user_config.items():
        # Check that user didn't add invalid keys to yaml file
        if k not in config:
            err_msg = f"User configuration contains invalid keys, check file:\n{user_config_fname}"
            raise ValueError(err_msg)
        config[k].update(d)

    log.debug(f"Config:\n{pformat(config)}")

    return config


def update_last_opened(path: str | Path) -> None:
    """Update the 'last_opened' key of the user configuration file"""
    # Get the path to the configuration file

    with open(USR_DIRS["CONFIG"] / "user_config.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    config["filenames"]["last_opened"] = str(Path(path).expanduser().resolve())

    with open(USR_DIRS["CONFIG"] / "user_config.yaml", "w", encoding="utf-8") as f:
        yaml.dump(config, stream=f)
        log.debug(f"Updated last opened file with:\n{path}")
