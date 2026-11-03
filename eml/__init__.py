"""Exercise Markup Language 1.0 reference implementation."""

from .data import Error, interface, load
from .program import Program

__all__ = ["Program", "Error", "interface", "load"]
