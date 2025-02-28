import sys
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QVBoxLayout,
    QPushButton,
    QListView,
    QTextEdit,
    QFileDialog,
    QMessageBox,
)
from PyQt6.QtGui import QStandardItemModel, QStandardItem


class FileDialogWidget(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("File Loader and Text Saver")
        self.resize(600, 400)

        # Main layout for the dialog.
        layout = QVBoxLayout(self)

        # Button to load files.
        self.loadButton = QPushButton("Load Files", self)
        self.loadButton.clicked.connect(self.load_files)
        layout.addWidget(self.loadButton)

        # ListView to display the names of the loaded files.
        self.fileListView = QListView(self)
        self.fileModel = QStandardItemModel(self.fileListView)
        self.fileListView.setModel(self.fileModel)
        layout.addWidget(self.fileListView)

        # A multi-line text input widget.
        self.textEdit = QTextEdit(self)
        layout.addWidget(self.textEdit)

        # Button to save the text from the textEdit.
        self.saveButton = QPushButton("Save Text", self)
        self.saveButton.clicked.connect(self.save_text)
        layout.addWidget(self.saveButton)

    def load_files(self):
        """
        Open a file dialog to select one or multiple files.
        The names of the selected files are added to the list view.
        """
        files, _ = QFileDialog.getOpenFileNames(self, "Select Files")
        if files:
            for file_path in files:
                # Extract the file name (or you could display the full path)
                file_name = file_path.split("/")[-1]
                item = QStandardItem(file_name)
                self.fileModel.appendRow(item)

    def save_text(self):
        """
        Open a file dialog to save the text currently in the textEdit.
        """
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Text File", "", "Text Files (*.txt);;All Files (*)")
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(self.textEdit.toPlainText())
                QMessageBox.information(self, "Success", "Text saved successfully.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save text: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    dialog = FileDialogWidget()
    dialog.show()
    sys.exit(app.exec())
