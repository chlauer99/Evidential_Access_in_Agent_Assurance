"""Progress of completed work items, also visible in pipeline log files."""
import os
import sys
from tqdm import tqdm


def completed(futures, total, label):
    title = os.environ.get("MAB_PROGRESS_LABEL", label)
    print("\n" + title + f" — {total} ausstehende Einheiten", flush=True)
    return tqdm(futures, total=total, desc=title, unit="Einheit", file=sys.stderr,
                disable=False, mininterval=1, ncols=110,
                bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]")
