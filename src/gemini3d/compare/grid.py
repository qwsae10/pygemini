from __future__ import annotations
from pathlib import Path
import numpy as np
import logging

from .utils import err_pct, load_tol
from .. import read


def compare_grid(
    new_dir: Path, refdir: Path, *, tol: dict[str, float] = None, file_format: str = None
) -> int:

    ref = read.grid(refdir)
    new = read.grid(new_dir, file_format=file_format)

    if not ref:
        raise FileNotFoundError(f"No simulation grid in {refdir}")
    if not new:
        raise FileNotFoundError(f"No simulation grid in {new_dir}")

    errs = 0

    if tol is None:
        tol = load_tol()

    for k in ref.keys():
        if not isinstance(ref[k], np.ndarray):
            continue

        assert (
            ref[k].shape == new[k].shape
        ), f"{k}: ref shape {ref[k].shape} != data shape {new[k].shape}"
        if not np.allclose(ref[k], new[k], rtol=tol["rtol"], atol=tol["atol"]):
            errs += 1
            logging.error(f"{k}  {err_pct(ref[k], new[k]):.1f} %")

    return errs