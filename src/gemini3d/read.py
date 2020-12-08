"""
struct manpage:
https://docs.python.org/3/library/struct.html#struct-format-strings
"""

import numpy as np
from pathlib import Path
from datetime import datetime
import typing as T

from .config import read_config as config
from .fileio import get_simsize
from .find import get_frame_filename, get_grid_filename
from . import matlab

from .raw import read as raw_read
from .hdf5 import read as h5read
from .nc4 import read as ncread


def grid(path: Path, file_format: str = None) -> T.Dict[str, np.ndarray]:

    fn = get_grid_filename(path)
    if not fn:
        return {}

    if not file_format:
        file_format = fn.suffix[1:]

    if file_format == "dat":
        grid = raw_read.grid(fn.with_suffix(".dat"))
    elif file_format == "h5":
        grid = h5read.grid(fn.with_suffix(".h5"))
    elif file_format == "nc":
        grid = ncread.grid(fn.with_suffix(".nc"))
    elif file_format == "mat":
        grid = matlab.grid(fn.with_suffix(".mat"))
    else:
        raise ValueError(f"Unknown file type {fn}")

    return grid


def data(
    fn: Path, file_format: str = None, *, cfg: T.Dict[str, T.Any] = None, E0dir: Path = None
) -> T.Dict[str, T.Any]:
    """
    knowing the filename for a simulation time step, read the data for that time step

    Parameters
    ----------
    fn: pathlib.Path
        filename for this timestep
    file_format: str
        specify file extension of data files
    cfg: dict
        to avoid reading config.nml
    E0dir: pathlib.Path
        E0 directory

    Returns
    -------
    dat: dict
        simulation outputs as numpy.ndarray
    """

    if not fn:
        return {}

    wavelength = [
        "3371",
        "4278",
        "5200",
        "5577",
        "6300",
        "7320",
        "10400",
        "3466",
        "7774",
        "8446",
        "3726",
        "LBH",
        "1356",
        "1493",
        "1304",
    ]

    fn = Path(fn).expanduser()
    fn_aurora = fn.parent / "aurmaps" / fn.name

    input_dir = fn.parent / "inputs"
    if not cfg:
        cfg = config(input_dir)

    if not file_format:
        file_format = fn.suffix[1:]

    if file_format == "dat":
        lxs = get_simsize(fn.parent / "inputs/simsize.dat")

        flag = cfg.get("flagoutput")
        if flag == 0:
            dat = raw_read.frame3d_curvne(fn, lxs)
        elif flag == 1:
            dat = raw_read.frame3d_curv(fn, lxs)
        elif flag == 2:
            dat = raw_read.frame3d_curvavg(fn, lxs)
        else:
            raise ValueError(f"Unsure how to read {fn} with flagoutput {flag}")

        if fn_aurora.is_file():
            dat.update(raw_read.glow_aurmap(fn_aurora, lxs, len(wavelength)))
            dat["wavelength"] = wavelength

    elif file_format == "h5":
        flag = h5read.flagoutput(fn, cfg)

        if flag == 0:
            dat = h5read.frame3d_curvne(fn)
        elif flag == 1:
            dat = h5read.frame3d_curv(fn)
        elif flag == 2:
            dat = h5read.frame3d_curvavg(fn)
        else:
            raise ValueError(f"Unsure how to read {fn} with flagoutput {flag}")

        if fn_aurora.is_file():
            dat.update(h5read.glow_aurmap(fn_aurora))
            dat["wavelength"] = wavelength
    elif file_format == "nc":
        flag = ncread.flagoutput(fn, cfg)

        if flag == 0:
            dat = ncread.frame3d_curvne(fn)
        elif flag == 1:
            dat = ncread.frame3d_curv(fn)
        elif flag == 2:
            dat = ncread.frame3d_curvavg(fn)
        else:
            raise ValueError(f"Unsure how to read {fn} with flagoutput {flag}")

        if fn_aurora.is_file():
            dat.update(ncread.glow_aurmap(fn_aurora))
            dat["wavelength"] = wavelength
    else:
        raise ValueError(f"Unknown file type {fn}")

    if E0dir:
        fn_Efield = E0dir / fn.name
        if fn_Efield.is_file():
            dat.update(Efield(fn_Efield))

    return dat


def Efield(fn: Path, file_format: str = None) -> T.Dict[str, T.Any]:
    """load Efield data "Efield_inputs"

    Parameters
    ----------
    fn: pathlib.Path
        filename for this timestep

    Returns
    -------
    dat: dict of np.ndarray
        electric field
    """

    if not fn:
        return {}

    fn = Path(fn).expanduser().resolve(strict=True)

    if not file_format:
        file_format = fn.suffix[1:]

    if file_format == "h5":
        E = h5read.Efield(fn)
    elif file_format == "nc":
        E = ncread.Efield(fn)
    elif file_format == "dat":
        E = raw_read.Efield(fn)
    else:
        raise ValueError(f"Unknown file type {fn}")

    return E


def precip(fn: Path, file_format: str = None) -> T.Dict[str, T.Any]:
    """load precipitation to disk

    Parameters
    ----------
    fn: pathlib.Path
        path to precipitation file
    file_format: str
        file format to read

    Returns
    -------
    dat: dict
        precipitation
    """

    if not fn:
        return {}

    fn = Path(fn).expanduser().resolve(strict=True)

    if not file_format:
        file_format = fn.suffix[1:]

    if file_format == "h5":
        dat = h5read.precip(fn)
    elif file_format == "nc":
        dat = ncread.precip(fn)
    else:
        raise ValueError(f"unknown file format {file_format}")

    return dat


def state(
    file: Path,
) -> T.Dict[str, T.Any]:
    """
    load inital condition data
    """

    if file.suffix == ".h5":
        dat = h5read.state(file)
    elif file.suffix == ".nc":
        dat = ncread.state(file)
    else:
        raise ValueError(f"unknown file format {file.suffix}")

    return dat


def frame(simdir: Path, time: datetime, file_format: str = None) -> T.Dict[str, T.Any]:
    """
    This is what users should normally use.
    load a frame of simulation data, automatically selecting the correct
    functions based on simulation parameters

    Parameters
    ----------
    simdir: pathlib.Path
        top-level directory of simulation output
    time: datetime.datetime
        time to load from simulation output
    file_format: str, optional
        "hdf5", "nc" for hdf5 or netcdf4 respectively

    Returns
    -------
    dat: dict
        simulation output for this time step
    """

    return data(get_frame_filename(simdir, time, file_format), file_format)