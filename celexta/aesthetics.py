"""Module containing color themes and other aesthetics related variables"""

from PyQt6.QtGui import QIcon, QPixmap, QColor
from zhunter.colors import mpl_rbga_to_pyqt_color
import numpy as np
import cmasher as cmr
from itertools import cycle
import logging
from typing import ClassVar

log = logging.getLogger(__name__)

__CELEXTA_LOGO__ = r"""
  ____     _           _
 / ___|___| | _____  _| |_ __ _
| |   / _ \ |/ _ \ \/ / __/ _` |
| |__|  __/ |  __/>  <| || (_| |
 \____\___|_|\___/_/\_\\__\__,_|
"""


def create_icon(color, size=(16, 16)):
    """Create a small colored square icon."""
    if isinstance(color, np.ndarray):
        color = mpl_rbga_to_pyqt_color(color)
    pixmap = QPixmap(*size)  # Create a 16x16 square
    pixmap.fill(color)  # Fill with the table color
    icon = QIcon(pixmap)  # Convert to QIcon
    return icon


def get_blues(n):

    b_colors = cmr.take_cmap_colors("cmr.freeze", n, cmap_range=(0.4, 0.8))
    return b_colors


def get_reds(n):
    r_colors = cmr.take_cmap_colors("cmr.ember", n, cmap_range=(0.4, 0.8))
    return r_colors


class ColorManager:
    """Manages assigning unique colors to items."""

    COLORS: ClassVar[list] = [
        "#4A9EBC",  # Lightblue
        "#ECCA54",  # Yellow
        "#C72A70",  # Pink
        "#C95D38",  # Orange
        "#92D754",  # Green
        "#8218BB",  # Purple
        "#66CBA0",  # Teal
        "#B52EB0",  # Fuschia
        "#2D67EE",  # Blue
        "#7E3817",  # Sangria
        "#C0C0C0",  # Silver
        "#808000",  # Olive
        "#49413F",  # Charcoal
        "#F9B7FF",  # Blossom Pink
        "#FFDF00",  # Golden yellow
        "#64E986",  # Algae
        "#16E2F5",  # Turquoise
    ]

    def __init__(self):
        self.reset_color_cycler()

    def get_color(self):
        """
        Get the next color from the list of available colors.

        If all colors have been used, reset the color cycler.
        """
        try:
            color = next(self.available_colors_cycler)
        except StopIteration:
            log.info("Exhausted all colors, resetting color cycler.")
            self.reset_color_cycler()
            color = next(self.available_colors_cycler)
        log.debug("There are %d unused colors left", len(self.available_colors))
        return color

    def reset_color_cycler(self):
        """Reset the color palet."""
        self.available_colors = self.COLORS.copy()
        self.available_colors_cycler = cycle(self.available_colors)

    def clear_color_from_available_pool(self, color):
        """Remove the color from the pool of available colors."""
        self.available_colors.remove(color)
        self.available_colors_cycler = cycle(self.available_colors)

    def add_color_to_available_pool(self, color):
        """Add the color from the pool of available colors."""
        self.available_colors.append(color)
        self.available_colors_cycler = cycle(self.available_colors)
