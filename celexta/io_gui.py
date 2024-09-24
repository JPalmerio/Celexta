"""Contains functions for reading and writing data from files."""

import logging
from pathlib import Path

from PyQt6 import QtCore, QtWidgets

log = logging.getLogger(__name__)


def open_file(parent: QtWidgets.QWidget, base_dir: Path | str | None = None, file_type: str = "(*)") -> str:
    """Open a file dialog and select a file.

    Parameters
    ----------
    parent : QWidget
        The parent widget.
    base_dir : Optional[str or Path]
        Path to the default directory in which to open the file dialog.
        If ``None``, the current directory will be used.
    file_type : str
        String containing the file types to consider. Example: "(*.dat *.txt *.csv)"

    Returns
    -------
    str
        Path to the selected file as a string.
    """
    log.debug("Selecting file to open")
    if base_dir is None:
        base_dir = QtCore.QDir.currentPath()
    log.debug(f"Opening file dialog in {base_dir!s}")
    dialog = QtWidgets.QFileDialog(parent)
    dialog.setWindowTitle("Open file")
    dialog.setNameFilter(file_type)
    dialog.setDirectory(str(base_dir))
    dialog.setFileMode(QtWidgets.QFileDialog.FileMode.ExistingFile)
    filename = None
    if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
        filename = dialog.selectedFiles()
    if filename:
        filename = str(filename[0])
        log.debug(f"Selected file: {filename}")
        return filename
    else:
        return ""


def save_file(
    parent: QtWidgets.QWidget, base_dir: Path | str | None = None, file_type: str = "All Files(*);;Text Files(*.txt)"
) -> str:
    """Open a file dialog and select a file in which to save.

    Parameters
    ----------
    parent : QWidget
        The parent widget.
    base_dir : Optional[str or Path]
        Path to the default directory in which to open the file dialog.
        If ``None``, the current directory will be used.
    file_type : str
        String containing the file types to consider. Example: "(*.dat *.txt *.csv)"

    Returns
    -------
    str
        Path to the selected file as a string.
    """
    log.debug("Selecting file")
    if base_dir is None:
        base_dir = QtCore.QDir.currentPath()
    log.debug(f"Opening file dialog in {base_dir!s}")
    filename, _ = QtWidgets.QFileDialog.getSaveFileName(
        parent=parent,
        caption="Save File",
        directory=str(base_dir),
        filter=file_type,
    )
    if filename:
        log.debug(f"Selected file: {filename}")
    else:
        log.debug("No selected file")
    return filename
