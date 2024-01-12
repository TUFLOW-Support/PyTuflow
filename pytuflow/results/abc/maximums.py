from abc import ABC


class Maximums(ABC):
    """Abstract base class for maximums."""

    def __init__(self, *args, **kwargs):
        self.df = None
