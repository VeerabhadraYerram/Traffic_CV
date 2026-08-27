#!/usr/bin/env python3
"""
Root convenience wrapper for mobile_stream/setup_mobile_stream.py.

Usage:
  python set_mobile_stream.py                            # Interactive Wizard
  python set_mobile_stream.py <STREAM_URL>               # Quick set URL (RTSP / HTTP / push)
  python set_mobile_stream.py <STREAM_URL> --camera "Gate 1"
"""

import sys
import os

# Delegate directly to mobile_stream/setup_mobile_stream.py
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "mobile_stream"))

from setup_mobile_stream import main

if __name__ == "__main__":
    main()
