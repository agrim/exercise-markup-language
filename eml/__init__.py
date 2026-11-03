"""Exercise Markup Language 1.1 reference implementation."""

from .data import Error, interface, load
from .program import Program

__all__ = ["Program", "Error", "interface", "load"]
