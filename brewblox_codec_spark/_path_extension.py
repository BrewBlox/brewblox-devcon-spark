"""
The Protobuf protoc compiler does not add relative imports for generated files.

In order to make direct top-level imports viable, the proto directory is added to path
"""

import os
import sys

PROTO_PATH = os.path.dirname(os.path.abspath(__file__)) + '/proto/'

if PROTO_PATH not in sys.path:
    sys.path.append(PROTO_PATH)


def avoid_lint_errors():
    """
    No-op function to avoid "unused import" linting errors.
    Marking the import with # noqa would achieve the same effect,
    but also disable IDE suggestions.
    """
    pass
