"""Experiment-local train.py — imports model.py/features.py from this directory."""
import sys
from pathlib import Path
HERE = Path(__file__).parent
TRAINING = HERE.parent
sys.path.insert(0, str(HERE))      # experiment overrides first
sys.path.append(str(TRAINING))     # base training dir as fallback

# Reuse base training logic after path is set
from train import load_examples, normalize_record, train, parse_args

if __name__ == "__main__":
    train(parse_args())
