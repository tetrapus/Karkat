"""
Karkat features.
Disable a plugin globally by removing it from __modules__.
"""

from . import google
from . import addgame
from . import shorten
from . import shell
from . import base
from . import suggest
from . import lastfm
from . import wolfram
from . import youtube
from . import spellchecker
from . import cardsagainsthumanity

__modules__ = [google,
               addgame,
               shorten,
               shell,
               base,
               suggest,
               lastfm,
               wolfram,
               youtube,
               spellchecker,
               cardsagainsthumanity]
