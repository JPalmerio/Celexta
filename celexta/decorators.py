"""Decorators used in celexta"""
import functools
import logging

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
