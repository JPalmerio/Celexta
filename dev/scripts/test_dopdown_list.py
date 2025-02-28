from PyQt6.QtWidgets import QApplication, QFrame, QPushButton, QListView, QVBoxLayout, QWidget
from PyQt6.QtCore import QStringListModel


class ExpandableDropdown(QWidget):
    """Custom dropdown that expands on button click with a caret indicator."""

    def __init__(self):
        super().__init__()

        # Toggle Button (Initially Points Right ▶)
        self.toggle_button = QPushButton("▶ Select Item")
        self.toggle_button.setFixedSize(120, 30)

        # List View (Hidden Initially)
        self.list_view = QListView()
        self.list_view.setFixedHeight(100)  # Set height for dropdown effect

        # Create a frame to act as the dropdown container
        self.dropdown_frame = QFrame()
        self.dropdown_layout = QVBoxLayout(self.dropdown_frame)
        self.dropdown_layout.addWidget(self.list_view)
        self.dropdown_frame.setVisible(False)  # Hide initially

        # Add items to the list view
        self.model = QStringListModel(["Item 1", "Item 2", "Item 3"])
        self.list_view.setModel(self.model)

        # Connect button click to toggle dropdown
        self.toggle_button.clicked.connect(self.toggle_dropdown)

        # Layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.toggle_button)
        layout.addWidget(self.dropdown_frame)

    def toggle_dropdown(self):
        """Toggle dropdown visibility and update caret direction."""
        is_open = self.dropdown_frame.isVisible()
        self.dropdown_frame.setVisible(not is_open)  # Show/hide frame

        # Update button text with caret indicator
        self.toggle_button.setText("▼ Select Item" if not is_open else "▶ Select Item")


# Run the application
if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    window = ExpandableDropdown()
    window.show()
    sys.exit(app.exec())
