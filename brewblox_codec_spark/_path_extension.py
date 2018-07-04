"""
The Protobuf protoc compiler does not add relative imports for generated files.

In order to make direct top-level imports viable, the proto directory is added to path
"""

import sys
import os


PROTO_PATH = os.path.dirname(os.path.abspath(__file__)) + '/proto/'
sys.path.append(PROTO_PATH)
