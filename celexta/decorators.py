"""Decorators used in celexta"""

import functools
import logging
from PyQt6.QtWidgets import QMessageBox

log = logging.getLogger(__name__)


def check_active(func):
    """Check that the widget (passed in self) is active before running the function."""

    @functools.wraps(func)
    def wrapper_check_active(self, *args, **kwargs):
        if not self.active:
            log.debug(f"Ignoring call to {func.__name__} as {self} is not active.")
            return None
        return func(self, *args, **kwargs)

    return wrapper_check_active


def requires_focused_frame(func):
    """Check that the widget (passed in self) has a frame before running the function.

    If no focused frame, will focus the last frame.
    If no frames, will create a new frame.
    """

    @functools.wraps(func)
    def wrapper_requires_focused_frame(self, *args, **kwargs):

        if self.focused_frame is None:
            if self.frames:
                self.focused_frame = self.frames[-1]
            else:
                frame = self.add_frame()
                self.focused_frame = frame
        return func(self, *args, **kwargs)

    return wrapper_requires_focused_frame


def requires_tab(func):
    """Check that the widget (passed in self) has a tab before running the function."""

    @functools.wraps(func)
    def wrapper_requires_tab(self, *args, **kwargs):
        if not self.tab_widget.currentWidget():
            return None
        return func(self, *args, **kwargs)

    return wrapper_requires_tab


def route_to_clicked_frame(func):
    """Determine which Frame was clicked and call the function on it."""

    @functools.wraps(func)
    def wrapper(self, event, *args, **kwargs):
        if hasattr(event, "inaxes"):
            for frame in self.frames:
                if frame.ax is event.inaxes:  # Check which frame was clicked
                    return func(self, frame, event, *args, **kwargs)  # Call the function with the correct frame
        # If it's a pick event, check the mouse event
        elif hasattr(event, "mouseevent"):
            for frame in self.frames:
                if frame.ax is event.mouseevent.inaxes:
                    return func(self, frame, event, *args, **kwargs)
        return None  # No frame found, do nothing

    return wrapper
