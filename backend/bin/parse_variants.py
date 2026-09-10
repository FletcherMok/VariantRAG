#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from variantrag.cli import main
sys.argv.insert(1, 'parse')
main()
