__version__ = "0.2.0"

# Avoid native OpenMP oversubscription/conflicts when PyTorch and FAISS share a process.
# Operators can explicitly set OMP_NUM_THREADS before starting a run.
import os

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
