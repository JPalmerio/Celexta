from PyQt6.QtWidgets import QApplication, QMainWindow, QTextEdit, QPushButton, QWidget, QVBoxLayout, QSplitter


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Create a splitter
        self.splitter = QSplitter()

        # Main content area
        self.main_content = QTextEdit("Main Content Here")

        # Side panel
        self.side_panel = QTextEdit("Side Panel Content")

        # Add widgets to splitter
        self.splitter.addWidget(self.main_content)
        self.splitter.addWidget(self.side_panel)

        # Add toggle button
        self.toggle_btn = QPushButton("Toggle Panel")
        self.toggle_btn.clicked.connect(self.toggle_panel)

        # Layout for the button
        button_container = QWidget()
        layout = QVBoxLayout(button_container)
        layout.addWidget(self.toggle_btn)
        self.setMenuWidget(button_container)  # Put button in menu bar area

        self.setCentralWidget(self.splitter)

    def toggle_panel(self):
        """Hide/show the side panel by resizing the splitter."""
        if self.side_panel.isVisible():
            self.side_panel.setVisible(False)  # Hide the panel
        else:
            self.side_panel.setVisible(True)  # Show the panel


# Run the application
if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
