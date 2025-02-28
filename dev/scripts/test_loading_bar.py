import sys
import logging
import time
import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QProgressBar
from PyQt6.QtCore import QThread, pyqtSignal, QObject

import atexit


def cleanup_logging(handler):
    logging.getLogger().removeHandler(handler)


class LogHandler(logging.Handler, QObject):
    """Custom log handler to emit progress updates from logs."""

    progressUpdated = pyqtSignal(int)  # Signal for progress updates

    def __init__(self):
        logging.Handler.__init__(self)  # Initialize logging.Handler
        QObject.__init__(self)  # Initialize QObject

    def emit(self, record):
        """Capture log messages and extract progress information."""
        msg = record.getMessage()
        if "Progress" in msg:  # Assuming logs contain "Progress: XX%"
            try:
                percent = int(msg.split("Progress: ")[1].replace("%", ""))
                self.progressUpdated.emit(percent)
            except ValueError:
                pass

    def close(self):
        """Properly remove the log handler before exit."""
        logging.getLogger().removeHandler(self)  # Remove from logging system
        super().close()


class ImageDownloader(QThread):
    """Simulated image downloader that logs progress."""

    downloadComplete = pyqtSignal(object)  # Signal for sending image data

    def run(self):
        """Simulate downloading an image with logging-based progress."""

        size = (500, 500)  # Example image size
        image_data = np.zeros(size)  # Placeholder

        for i in range(1, 101):
            time.sleep(0.01)  # Simulate network delay
            logging.info(f"Progress: {i}%")  # Log progress

        # Simulated image loading
        image_data[:] = np.random.normal(size=size)
        self.downloadComplete.emit(image_data)  # Emit final image


class ImageViewer(QWidget):
    """GUI that captures progress from logs."""

    def __init__(self):
        super().__init__()

        # Layout
        self.layout = QVBoxLayout(self)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.hide()

        # Load Button
        self.load_button = QPushButton("Load Image")
        self.load_button.clicked.connect(self.start_download)

        # Image Viewer
        self.image_view = pg.ImageView()

        # Add widgets
        self.layout.addWidget(self.progress_bar)
        self.layout.addWidget(self.load_button)
        self.layout.addWidget(self.image_view)

        # Setup log handler to capture progress
        self.log_handler = LogHandler()
        self.log_handler.progressUpdated.connect(self.progress_bar.setValue)
        logging.getLogger().addHandler(self.log_handler)  # Attach log handler
        atexit.register(cleanup_logging, self.log_handler)  # Unregister handler before exit

    def start_download(self):
        """Start image download in a separate thread."""
        self.progress_bar.show()
        self.progress_bar.setValue(0)

        self.worker = ImageDownloader()
        self.worker.downloadComplete.connect(self.display_image)
        self.worker.start()

    def display_image(self, image_data):
        """Show image and hide progress bar."""
        self.image_view.setImage(image_data)
        self.progress_bar.hide()

    def closeEvent(self, event):
        """Properly clean up logging before the application exits."""
        logging.getLogger().removeHandler(self.log_handler)  # Remove handler
        self.log_handler.close()
        self.log_handler.deleteLater()  # Ensure PyQt removes the QObject safely
        self.log_handler = None
        event.accept()  # Proceed with closing


# Run the application
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)  # Enable logging
    app = QApplication(sys.argv)
    window = ImageViewer()
    window.show()
    sys.exit(app.exec())
