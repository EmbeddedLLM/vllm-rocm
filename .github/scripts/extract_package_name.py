#!/usr/bin/env python3
"""
Extract normalized package name from wheel filename.
"""
import sys
from pathlib import Path

try:
    from packaging.utils import parse_wheel_filename

    wheel_name = sys.argv[1] if len(sys.argv) > 1 else ""

    try:
        name, version, build, tags = parse_wheel_filename(wheel_name)
        # Normalize package name per PEP 503
        print(name.lower().replace('_', '-').replace('.', '-'))
    except Exception:
        # Fallback to simple parsing
        print(wheel_name.split('-')[0].lower().replace('_', '-'))

except ImportError:
    # If packaging module not available, use simple fallback
    wheel_name = sys.argv[1] if len(sys.argv) > 1 else ""
    print(wheel_name.split('-')[0].lower().replace('_', '-'))
