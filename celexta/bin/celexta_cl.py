"""
Module containing the various command-line executables.

Authors:
    * Jesse Palmerio, jesse.palmerio@obspm.fr

"""

import argparse
import sys

from PyQt6 import QtWidgets

import celexta.initialize as init
from celexta import __version__
from celexta.aesthetics import __CELEXTA_LOGO__
from celexta.main_gui import MainGUI

# Define root logger
log = init.default_logging()


def get_celexta_cli_args():
    """
    Retrieve command line options for the `celexta` executable.

    Returns
    -------
    parser.parse_args: argparse.Namespace
        Namespace containing each argument with its associated value.
    """
    parser = argparse.ArgumentParser(add_help=True, description="Launch the celexta Graphical User Interface")

    return parser.parse_args()


def main():
    """Launch the celexta GUI app"""
    # Retrieve the command line arguments
    # args = get_celexta_cli_args()
    log.info("\n" + 36 * "-" + __CELEXTA_LOGO__ + "\n" + 14 * " " + f"v{__version__}\n" + 36 * "-")

    # Load config
    config = init.load_config()

    # Update logging
    init.update_logging(
        log_level=config["logging"]["log_level"],
        log_file=config["logging"]["log_file"],
    )

    log.info("Launching GUI...")
    app = QtWidgets.QApplication(sys.argv)
    gui = MainGUI(config=config)
    gui.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
