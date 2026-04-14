#!/usr/bin/env python3
"""gemma-cli — 로컬 AI CLI 진입점"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app.main import main

if __name__ == "__main__":
    main()
