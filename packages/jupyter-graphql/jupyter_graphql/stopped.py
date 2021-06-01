import enum

__all__ = ["Stopped", "_stopped"]

# Sentinel to signal stopped iterator
# https://www.python.org/dev/peps/pep-0484/#support-for-singleton-types-in-unions
class Stopped(enum.Enum):
    token = 0


_stopped = Stopped.token
