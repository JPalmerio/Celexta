import logging

from PyQt6.QtWidgets import QMessageBox

log = logging.getLogger(__name__)


def show_error_popup(title, text, error_message):
    """Display an error pop-up with the given message."""
    error_popup = QMessageBox()
    error_popup.setIcon(QMessageBox.Icon.Critical)
    error_popup.setWindowTitle(title)
    error_popup.setText(text)
    error_popup.setInformativeText(error_message)
    error_popup.setStandardButtons(QMessageBox.StandardButton.Ok)
    error_popup.exec()


def show_warning_popup(title, text, warning_message):
    """Display a warning pop-up with the given message."""
    warning_popup = QMessageBox()
    warning_popup.setIcon(QMessageBox.Icon.Warning)
    warning_popup.setWindowTitle(title)
    warning_popup.setText(text)
    warning_popup.setInformativeText(warning_message)
    warning_popup.setStandardButtons(QMessageBox.StandardButton.Ok)
    warning_popup.exec()
