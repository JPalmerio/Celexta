"""Initialize celexta directories"""

import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

__version__ = "0.0.1"

__CELEXTA_SRC_DIR__ = Path(__file__).parent.expanduser().resolve()
__CELEXTA_DIR__ = Path("~/.celexta").expanduser().resolve()

log.debug(f"CELEXTA_SRC_DIR: {__CELEXTA_SRC_DIR__}")
