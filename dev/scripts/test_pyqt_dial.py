from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QDial
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt


class AngleSelector(QWidget):
    """Custom widget to select an angle with a dial and a spin box."""

    def __init__(self):
        super().__init__()

        # Create layout
        main_layout = QVBoxLayout()
        control_layout = QHBoxLayout()

        # Circular Dial
        self.dial = QDial()
        self.dial.setRange(0, 360)  # Set range from 0° to 360°
        self.dial.setNotchesVisible(True)  # Show notches
        self.dial.setWrapping(False)  # Prevent full rotation
        self.dial.setFixedSize(40, 40)  # Match UI size

        # Angle Spin Box
        self.angle_spinbox = QSpinBox()
        self.angle_spinbox.setSuffix("°")  # Add degree symbol
        self.angle_spinbox.setRange(0, 360)  # Set range from 0° to 360°
        self.angle_spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)  # Center align text

        # Connect dial and spin box
        self.dial.valueChanged.connect(self.angle_spinbox.setValue)
        self.angle_spinbox.valueChanged.connect(self.dial.setValue)

        # Label Below
        self.label = QLabel("Angle")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setFon(QFont("Arial", 10, QFont.Weight.Bold))  # Adjust font size & weight

        # Add widgets to layouts
        control_layout.addWidget(self.dial)
        control_layout.addWidget(self.angle_spinbox)

        main_layout.addLayout(control_layout)
        main_layout.addWidget(self.label)

        # Set final layout
        self.setLayout(main_layout)


# Example usage in a standalone PyQt application
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    window = AngleSelector()
    window.show()
    sys.exit(app.exec())
