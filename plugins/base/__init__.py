"""
Karkat's base features.

It is recommended you do not disable any of these features, however none of
them are critical.
"""

from . import autojoin
from . import botmode
from . import interpreter
from . import autorejoin
from . import modulemanager
from . import ctcp
from . import restart

__modules__ = [autojoin,
               botmode,
               interpreter,
               autorejoin,
               modulemanager,
               ctcp,
               restart]
