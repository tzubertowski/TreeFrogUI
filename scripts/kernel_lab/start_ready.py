"""Launch the frozen, prechecked acceptance suite from this bundle."""
import os
from pathlib import Path
import sys

bundle = Path(__file__).resolve().parent
os.environ["R36_PROJECT_ROOT"] = str(bundle.parents[1])
sys.path.insert(0, str(bundle / "tools"))
from acceptance import main

if __name__ == "__main__":
    sys.argv = [sys.argv[0], "--bundle", str(bundle), *sys.argv[1:]]
    sys.exit(main())
