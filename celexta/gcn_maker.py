"""Contains the GCN maker ui"""

import logging
import shutil
from pathlib import Path
from typing import List, Optional, Tuple
import pandas as pd
from PyQt6 import QtWidgets, QtCore

from celexta.initialize import SRC_DIRS, USR_DIRS
from celexta.io_gui import open_file, save_file
from celexta.windows import Ui_GcnMakerWindow

log = logging.getLogger(__name__)

GCN_MAKER_DIR = USR_DIRS["GCN_MAKER"]
DEFAULT_AUTHOR_TABLE = GCN_MAKER_DIR / "GCN_authors.csv"
Author = Tuple[str, str]
Authors = List[Author]


class GcnMakerWindow(QtWidgets.QDialog, Ui_GcnMakerWindow):
    def __init__(self, parent, authors_fname: str | Path | None = None):
        super(GcnMakerWindow, self).__init__(parent)
        log.info("Initializing GCN maker")
        self.parent = parent
        self.setupUi(self)
        self.create_dir()
        self.author_model = AuthorModel()
        self.comboBox_author.setModel(self.author_model)
        self.connect_buttons()
        # Will look for default GCN_authors.csv if authors_fname is None
        self.load_authors(fname=authors_fname)

    def connect_buttons(self):
        """Connect buttons with signals"""
        self.btn_load_template.clicked.connect(self.load_template)
        self.btn_save_template.clicked.connect(self.save_template)
        self.btn_add_author.clicked.connect(self.add_author)

    # Authors
    def load_authors(self, fname: Optional[str | Path] = None) -> None:
        """Load author table from input file"""
        # If no filename provided, use default author table
        if fname is None:
            fname = DEFAULT_AUTHOR_TABLE

        # Make sure fname is a Path instance
        fname = Path(fname)
        # Try to load author table with pandas
        try:
            df = pd.read_csv(fname)
            # Turn dataframe into list of (name, affiliation)
            self.author_model.update_authors(list(df.itertuples(index=False, name=None)))
            self.author_model.filename = fname
        except Exception as e:
            msg = f"Could not load authors because: {e!s}\n"
            "Expected a csv file with 2 columns: name,affiliations"
            log.exception(msg)
            QtWidgets.QMessageBox.information(
                self,
                "Could not load authors",
                msg,
            )
            return

    def add_author(self) -> None:
        """ Add new author to the authors list from the user input
        """
        index = self.comboBox_author.currentIndex()
        log.debug(f"Author combobox index: {index}")
        if index < 0:
            log.debug("Invalid index, ignoring")
            return
        name = self.author_model.get_name_w_affiliation(index)
        if name:
            log.debug(f"Author name to add: '{name!s}'")
            self.update_author_list(name)
            self.comboBox_author.setCurrentIndex(0)
        else:
            log.debug("No name, nothing to do.")

    def update_author_list(self, name: str) -> None:
        """Update author list with new name and affiliation

        Parameters
        ----------
        name : str
            String containing the name and affiliation to add to the list.
        """
        author_list = self.plainTextEdit_authors.toPlainText()
        author_list += ", " + str(name)
        author_list = author_list.strip(" ,")  # strip any whitespaces or commas
        self.plainTextEdit_authors.setPlainText(author_list)
        # Clear the lineEdit
        self.comboBox_author.clear()

    def save_template(self):
        """Save text in plainTextEdit_gcn as template"""
        log.debug("Saving current GCN text as template")

        fname = save_file(
            self,
            base_dir=GCN_MAKER_DIR / "templates",
            file_type="All Files(*);;Text Files(*.txt)",
        )
        # If no file selected, do nothing
        if not fname:
            log.debug("No file selected, doing nothing")
            return

        text = self.plainTextEdit_gcn.toPlainText()
        log.info(f"Saving current GCN text as template in: '{fname!s}'")
        with open(fname, "w", encoding="utf-8") as f:
            f.write(text)

    def load_template(self):
        """Load template in plainTextEdit_gcn"""
        log.debug("Loading GCN template")

        fname = open_file(
            self,
            base_dir=GCN_MAKER_DIR / "templates",
            file_type="All Files(*);;Text Files(*.txt)",
        )
        # If no file selected, do nothing
        if not fname:
            log.debug("No file selected, doing nothing")
            return

        log.info(f"Loading template from: '{fname!s}'")
        with open(fname, encoding="utf-8") as f:
            text = f.read()

        self.plainTextEdit_gcn.setPlainText(text)
        self.setFocus()

        w = self.focusWidget()
        log.info(f"Focus: {w}")

    @staticmethod
    def create_dir():
        """Create directories if they don't exist"""
        # Make sure templates directory exists
        templates_dir = GCN_MAKER_DIR / "templates"
        templates_dir.mkdir(exist_ok=True, parents=True)
        if not DEFAULT_AUTHOR_TABLE.exists():
            log.debug("Default author table not found, copying from source.")
            shutil.copyfile(SRC_DIRS["CONFIG"] / "GCN_authors.csv", DEFAULT_AUTHOR_TABLE)


class AuthorModel(QtCore.QAbstractListModel):
    def __init__(self, authors: Optional[Authors] = None):
        super().__init__()
        self.authors = authors or [('', '')]
        self.filename = None

    @staticmethod
    def _get_family_name(author: Author):
        names = author[0].split()
        if names:
            return names[-1]
        else:
            log.debug(f"No family name found for author '{author!s}', returning '{author[0]!s}'")
            # If no family name, its probably empty string
            return author[0]

    def update_authors(self, authors: Authors):
        self.authors += authors
        self.authors.sort(key=self._get_family_name)

    def data(self, index, role):
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            name, affiliation = self.authors[index.row()]
            return name
        if role == QtCore.Qt.ItemDataRole.EditRole:
            name, affiliation = self.authors[index.row()]
            return name

    def get_name_w_affiliation(self, index: int) -> str:
        """ Get author name and affiliation

        Parameters
        ----------
        index : int
            Index of the author.

        Returns
        -------
        str
            String of the concatenated author name and affiliation.
        """
        name, affiliation = self.authors[index]
        if name:
            return f"{name}" + f" ({affiliation})"
        else:
            return ''

    def rowCount(self, index):
        return len(self.authors)
