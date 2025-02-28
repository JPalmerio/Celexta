import sys
import io

from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget
from PyQt6.QtGui import QPixmap
import matplotlib.pyplot as plt


def latex_to_pixmap(latex_string, dpi=300):
    """
    Render a LaTeX string to a QPixmap using Matplotlib.

    Parameters:
        latex_string (str): The LaTeX code (without the dollar signs is fine,
                            as we add them in the code) to render.
        dpi (int): Dots per inch for the rendered image (controls resolution).

    Returns:
        QPixmap: The pixmap containing the rendered LaTeX.
    """
    # Create a figure with no axes
    fig = plt.figure(figsize=(0.01, 0.01))  # size will be adjusted with bbox_inches
    # Add text to the figure. We wrap the LaTeX string with '$' to tell Matplotlib it's math.
    fig.text(0, 0, f"${latex_string}$", fontsize=20)

    # Remove axes and extra white space
    plt.axis("off")

    # Save the figure to a BytesIO buffer
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", dpi=dpi, transparent=True)
    plt.close(fig)
    buf.seek(0)

    # Create a QPixmap from the PNG image data
    pixmap = QPixmap()
    pixmap.loadFromData(buf.getvalue(), "PNG")
    return pixmap


class LaTeXWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LaTeX Rendering Example")

        # Create a QLabel that will display our rendered LaTeX
        self.label = QLabel()

        # Render a LaTeX string into a QPixmap and set it on the label
        # For example, render a fraction:
        pixmap = latex_to_pixmap(r"\frac{a}{b} = \sqrt{c}")
        self.label.setPixmap(pixmap)

        # Layout the label in the window
        layout = QVBoxLayout()
        layout.addWidget(self.label)
        self.setLayout(layout)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LaTeXWidget()
    window.resize(400, 200)
    window.show()
    sys.exit(app.exec())
