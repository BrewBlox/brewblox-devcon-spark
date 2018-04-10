"""
Pyserial tries to import and use the 'logger' module.
While this exists on pip, it has the side effect of setting log settings at import.

This pre-empts brewblox_service logging configuration.

We can override this behavior by not installing the pip logger, but declaring it ourself.
"""

import logging
import sys

LOGGER = logging.getLogger(__name__)

sys.modules[__name__] = LOGGER
