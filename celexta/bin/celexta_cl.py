"""
Module containing the various command-line executables.

Authors:
    * Jesse Palmerio, jesse.palmerio@obspm.fr

"""

import argparse
import logging
import sys
from pprint import pformat

import celexta.initialize as init
from celexta import __version__
from celexta.aesthetics import __CELEXTA_LOGO__

# Define root logger
log = logging.getLogger()
s_hdlr = logging.StreamHandler(stream=sys.stdout)
s_hdlr.setFormatter(init.FORMATTER)
log.addHandler(s_hdlr)
log.setLevel(logging.DEBUG)


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
    log.info(
            "\n"
            + 36 * "-"
            + __CELEXTA_LOGO__
            + "\n"
            + 14 * " " + f"v{__version__}\n"
            + 36 * "-"
        )

    # Load config
    config = init.load_config()

    # Update logging
    init.update_logging(
        log_level=config["logging"]["log_level"],
        log_file=config["logging"]["log_file"],
    )

    log.info("Launching GUI...")


if __name__ == "__main__":
    main()
