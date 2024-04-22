"""Initialize celexta directory"""
import logging
from pathlib import Path

log = logging.getLogger(__name__)

__version__ = "0.0.1"

__CELEXTA_DIR__ = Path(__file__).parent
log.debug(f"CELEXTA_DIR: {__CELEXTA_DIR__}")
