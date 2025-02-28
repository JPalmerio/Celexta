from PyQt6.QtWidgets import QApplication, QMainWindow, QDockWidget, QTextEdit, QPushButton, QWidget, QVBoxLayout


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Create main widget
        self.central_widget = QTextEdit("Main Content Here")
        self.setCentralWidget(self.central_widget)

        # Create a dockable panel
        self.dock = QDockWidget("Side Panel", self)
        self.dock.setWidget(QTextEdit("Panel Content"))  # Example content
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock)

        # Add a button to toggle panel visibility
        toggle_btn = QPushButton("Toggle Panel")
        toggle_btn.clicked.connect(self.toggle_panel)

        # Wrap button inside a QWidget
        button_container = QWidget()
        layout = QVBoxLayout(button_container)
        layout.addWidget(toggle_btn)
        self.setMenuWidget(button_container)  # Put button in the menu area

    def toggle_panel(self):
        """Toggle the visibility of the side panel."""
        self.dock.setVisible(not self.dock.isVisible())  # Show/hide panel


# Run the application
if __name__ == "__main__":
    import sys
    from PyQt6.QtCore import Qt

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
