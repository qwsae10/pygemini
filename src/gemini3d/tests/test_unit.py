"""
unit tests of non-Fortran modules
"""

from pytest import approx
import numpy as np

import gemini3d.mpi as gm
import gemini3d.grid as grid


def test_grid1d():
    x = grid.grid1d(100.0, 5)
    assert x == approx(np.arange(-100, 125, 25.0), rel=1e-6, abs=1e-8)

    x = grid.grid1d(100.0, 5, [200, 0.5, 9.5, 10])
    assert x == approx(
        [-50.25, -40.25, -30.25, -20.25, -10.25, -0.25, 0.25, 10.25, 20.25, 30.25, 40.25, 50.25],
        rel=1e-6,
        abs=1e-8,
    )


def test_max_mpi():
    assert gm.max_mpi([48, 1, 40], 5) == 5
    assert gm.max_mpi([48, 40, 1], 5) == 5
    assert gm.max_mpi([48, 1, 40], 6) == 5
    assert gm.max_mpi([48, 40, 1], 6) == 5
    assert gm.max_mpi([48, 1, 40], 8) == 8
    assert gm.max_mpi([48, 40, 1], 8) == 8
    assert gm.max_mpi([48, 1, 40], 28) == 20
    assert gm.max_mpi([48, 40, 1], 28) == 20
    assert gm.max_mpi([48, 40, 36], 28) == 18
