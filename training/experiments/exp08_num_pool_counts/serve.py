"""Experiment-local serve.py — imports model.py/features.py from this directory."""
import sys
from pathlib import Path
HERE = Path(__file__).parent
TRAINING = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.append(str(TRAINING))

from serve import serve, load_model
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    serve(parser.parse_args())
