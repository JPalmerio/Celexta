import logging

from PyQt6.QtGui import QKeySequence, QShortcut
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar

log = logging.getLogger(__name__)


def create_mpl_toolbar(canvas: FigureCanvas, parent=None) -> NavigationToolbar:
    """Create the standard Matplotlib toolbar and add the keyboard shortcuts."""
    log.debug("Creating standard Matplotlib toolbar with keyboard shortcuts.")
    toolbar = NavigationToolbar(canvas=canvas, parent=parent)
    QShortcut(QKeySequence("h"), canvas).activated.connect(toolbar.home)
    # Pan toggle => p key
    QShortcut(QKeySequence("p"), canvas).activated.connect(toolbar.pan)
    # Zoom toggle => o key
    QShortcut(QKeySequence("o"), canvas).activated.connect(toolbar.zoom)
    # Save figure => Ctrl+S
    # QShortcut(QKeySequence(QKeySequence.StandardKey.Save), canvas).activated.connect(toolbar.save_figure)
    # Navigation Back => Left Arrow key
    QShortcut(QKeySequence("Left"), canvas).activated.connect(toolbar.back)
    # Navigation Forward => Right Arrow key
    QShortcut(QKeySequence("Right"), canvas).activated.connect(toolbar.forward)

    # Set the toolbar hight
    toolbar.setFixedHeight(25)  # Reduce height to 25 pixels
    # toolbar.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    return toolbar
