import logging

import astropy.units as u
import numpy as np
import zhunter.catalogs as cat
from astropy.coordinates import SkyCoord
from astropy.table import Table
from astropy.units import Quantity
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)


def create_input_field(unit_options, text=""):
    """Create an input field and unit dropdown, ensuring proper alignment."""
    input_field = QLineEdit(text)
    input_field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    input_field.setFixedWidth(120)

    unit_combo = QComboBox()
    unit_combo.addItems(unit_options)
    unit_combo.setFixedWidth(100)

    return input_field, unit_combo
