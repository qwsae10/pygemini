from pathlib import Path
import typing as T
import numpy as np
import logging
from datetime import datetime

from .utils import datetime2ymd_hourdec, ymdhourdec2datetime

try:
    import h5py
except ImportError:
    # must be ImportError not ModuleNotFoundError for botched HDF5 linkage
    h5py = None

LSP = 7


def get_simsize(path: Path) -> T.Tuple[int, ...]:
    """
    get simulation size
    """

    if h5py is None:
        raise ImportError("pip install h5py")

    path = Path(path).expanduser().resolve()

    with h5py.File(path, "r") as f:
        if "lxs" in f:
            lxs = f["lxs"][:]
        elif "lx" in f:
            lxs = f["lx"][:]
        elif "lx1" in f:
            if f["lx1"].ndim > 0:
                lxs = np.array(
                    [
                        f["lx1"][:].squeeze()[()],
                        f["lx2"][:].squeeze()[()],
                        f["lx3"][:].squeeze()[()],
                    ]
                )
            else:
                lxs = np.array([f["lx1"][()], f["lx2"][()], f["lx3"][()]])
        else:
            raise KeyError(f"could not find '/lxs', '/lx' or '/lx1' in {path.as_posix()}")

    return lxs


def read_state(fn: Path) -> T.Dict[str, T.Any]:
    """
    load initial condition data
    """

    if h5py is None:
        raise ImportError("pip install h5py")

    with h5py.File(fn, "r") as f:
        return {"ns": f["/nsall"][:], "vs": f["/vs1all"][:], "Ts": f["/Tsall"][:]}


def write_state(time: datetime, ns: np.ndarray, vs: np.ndarray, Ts: np.ndarray, fn: Path):
    """
    write STATE VARIABLE initial conditions

    NOTE THAT WE don't write ANY OF THE ELECTRODYNAMIC
    VARIABLES SINCE THEY ARE NOT NEEDED TO START THINGS
    UP IN THE FORTRAN CODE.

    INPUT ARRAYS SHOULD BE TRIMMED TO THE CORRECT SIZE
    I.E. THEY SHOULD NOT INCLUDE GHOST CELLS

    NOTE: The .transpose() reverses the dimension order.
    The HDF Group never implemented the intended H5T_array_create(..., perm)
    and it's deprecated.
    Fortran, including the HDF Group Fortran interfaces and h5fortran as well as
    Matlab read/write HDF5 in Fortran order. h5py read/write HDF5 in C order so we
    need the .transpose() for h5py
    """

    if h5py is None:
        raise ImportError("pip install h5py")

    logging.info(f"write_state: {fn}")

    with h5py.File(fn, "w") as f:
        f["/time/ymd"] = [time.year, time.month, time.day]
        f["/time/UTsec"] = (
            time.hour * 3600 + time.minute * 60 + time.second + time.microsecond / 1e6
        )

        p4 = (0, 3, 2, 1)
        # we have to reverse axes order and put lsp at the last dim

        f.create_dataset(
            "/nsall",
            data=ns.transpose(p4),
            dtype=np.float32,
            compression="gzip",
            compression_opts=1,
            shuffle=True,
            fletcher32=True,
        )
        f.create_dataset(
            "/vs1all",
            data=vs.transpose(p4),
            dtype=np.float32,
            compression="gzip",
            compression_opts=1,
            shuffle=True,
            fletcher32=True,
        )
        f.create_dataset(
            "/Tsall",
            data=Ts.transpose(p4),
            dtype=np.float32,
            compression="gzip",
            compression_opts=1,
            shuffle=True,
            fletcher32=True,
        )


def write_data(dat: T.Dict[str, T.Any], outfn: Path):
    """
    write simulation data
    e.g. for converting a file format from a simulation
    """

    if h5py is None:
        raise ImportError("pip install h5py")

    lxs = dat["lxs"]

    with h5py.File(outfn, "w") as h:
        for k in ["ns", "vs1", "Ts"]:
            if k not in dat:
                continue

            h.create_dataset(
                k,
                data=dat[k][1].astype(np.float32),
                chunks=(1, *lxs[1:], LSP),
                compression="gzip",
                compression_opts=1,
            )

        for k in ["ne", "v1", "Ti", "Te", "J1", "J2", "J3", "v2", "v3"]:
            if k not in dat:
                continue

            h.create_dataset(
                k,
                data=dat[k][1].astype(np.float32),
                chunks=(1, *lxs[1:]),
                compression="gzip",
                compression_opts=1,
            )

        if "Phitop" in dat:
            h.create_dataset(
                "Phitop",
                data=dat["Phitop"][1],
                compression="gzip",
                compression_opts=1,
            )


def readgrid(fn: Path) -> T.Dict[str, np.ndarray]:
    """
    get simulation grid

    Parameters
    ----------
    fn: pathlib.Path
        filepath to simgrid.h5

    Returns
    -------
    grid: dict
        grid parameters

    Transpose on read to undo the transpose operation we had to do in write_grid C => Fortran order.
    """

    if h5py is None:
        raise ImportError("pip install h5py")

    grid: T.Dict[str, T.Any] = {}

    if not fn.is_file():
        logging.error(f"{fn} grid file is not present.")
        return grid

    with h5py.File(fn, "r") as f:
        for k in f.keys():
            if f[k].ndim >= 2:
                grid[k] = f[k][:].transpose()
            else:
                grid[k] = f[k][:]

    try:
        grid["lxs"] = get_simsize(fn.with_name("simsize.h5"))
    except FileNotFoundError:
        grid["lxs"] = np.array([grid["x1"].size, grid["x2"].size, grid["x3"].size])

    return grid


def write_grid(size_fn: Path, grid_fn: Path, xg: T.Dict[str, T.Any]):
    """writes grid to disk

    Parameters
    ----------

    size_fn: pathlib.Path
        file to write
    grid_fn: pathlib.Path
        file to write
    xg: dict
        grid values

    NOTE: The .transpose() reverses the dimension order.
    The HDF Group never implemented the intended H5T_array_create(..., perm)
    and it's deprecated.
    Fortran, including the HDF Group Fortran interfaces and h5fortran as well as
    Matlab read/write HDF5 in Fortran order. h5py read/write HDF5 in C order so we
    need the .transpose() for h5py
    """

    if h5py is None:
        raise ImportError("pip install h5py")

    if "lx" not in xg:
        xg["lx"] = np.array([xg["x1"].shape, xg["x2"].shape, xg["x3"].shape])

    logging.info(f"write_grid: {size_fn}")
    with h5py.File(size_fn, "w") as h:
        h["/lx"] = xg["lx"]

    logging.info(f"write_grid: {grid_fn}")
    with h5py.File(grid_fn, "w") as h:
        for i in (1, 2, 3):
            for k in (
                f"x{i}",
                f"x{i}i",
                f"dx{i}b",
                f"dx{i}h",
                f"h{i}",
                f"h{i}x1i",
                f"h{i}x2i",
                f"h{i}x3i",
                f"gx{i}",
                f"e{i}",
            ):
                if k not in xg:
                    logging.info(f"SKIP: {k}")
                    continue

                if xg[k].ndim >= 2:
                    h.create_dataset(
                        f"/{k}",
                        data=xg[k].transpose(),
                        dtype=np.float32,
                        compression="gzip",
                        compression_opts=1,
                        shuffle=True,
                        fletcher32=True,
                    )
                else:
                    h[f"/{k}"] = xg[k].astype(np.float32)

        for k in (
            "alt",
            "glat",
            "glon",
            "Bmag",
            "I",
            "nullpts",
            "er",
            "etheta",
            "ephi",
            "r",
            "theta",
            "phi",
            "x",
            "y",
            "z",
        ):
            if k not in xg:
                logging.info(f"SKIP: {k}")
                continue

            if xg[k].ndim >= 2:
                h.create_dataset(
                    f"/{k}",
                    data=xg[k].transpose(),
                    dtype=np.float32,
                    compression="gzip",
                    compression_opts=1,
                    shuffle=True,
                    fletcher32=True,
                )
            else:
                h[f"/{k}"] = xg[k].astype(np.float32)


def read_Efield(fn: Path) -> T.Dict[str, T.Any]:
    """
    load electric field
    """

    if h5py is None:
        raise ImportError("pip install h5py")

    # sizefn = fn.with_name("simsize.h5")  # NOT the whole sim simsize.dat
    # with h5py.File(sizefn, "r") as f:
    #     E["llon"] = f["/llon"][()]
    #     E["llat"] = f["/llat"][()]

    gridfn = fn.with_name("simgrid.h5")  # NOT the whole sim simgrid.dat
    with h5py.File(gridfn, "r") as f:
        E = {"mlon": f["/mlon"][:], "mlat": f["/mlat"][:]}

    with h5py.File(fn, "r") as f:
        E["flagdirich"] = f["flagdirich"]
        for p in ("Exit", "Eyit", "Vminx1it", "Vmaxx1it"):
            E[p] = (("x2", "x3"), f[p][:])
        for p in ("Vminx2ist", "Vmaxx2ist"):
            E[p] = (("x2",), f[p][:])
        for p in ("Vminx3ist", "Vmaxx3ist"):
            E[p] = (("x3",), f[p][:])

    return E


def write_Efield(outdir: Path, E: T.Dict[str, np.ndarray]):
    """
    write Efield to disk
    """

    if h5py is None:
        raise ImportError("pip install h5py")

    with h5py.File(outdir / "simsize.h5", "w") as f:
        f["/llon"] = E["llon"]
        f["/llat"] = E["llat"]

    with h5py.File(outdir / "simgrid.h5", "w") as f:
        f["/mlon"] = E["mlon"].astype(np.float32)
        f["/mlat"] = E["mlat"].astype(np.float32)

    for i, t in enumerate(E["time"]):
        fn = outdir / (datetime2ymd_hourdec(t) + ".h5")

        # FOR EACH FRAME WRITE A BC TYPE AND THEN OUTPUT BACKGROUND AND BCs
        with h5py.File(fn, "w") as f:
            f["/flagdirich"] = E["flagdirich"][i].astype(np.int32)
            f["/time/ymd"] = [t.year, t.month, t.day]
            f["/time/UTsec"] = t.hour * 3600 + t.minute * 60 + t.second + t.microsecond / 1e6

            for k in ("Exit", "Eyit", "Vminx1it", "Vmaxx1it"):
                f.create_dataset(
                    f"/{k}",
                    data=E[k][i, :, :].transpose(),
                    dtype=np.float32,
                    compression="gzip",
                    compression_opts=1,
                    shuffle=True,
                    fletcher32=True,
                )
            for k in ("Vminx2ist", "Vmaxx2ist", "Vminx3ist", "Vmaxx3ist"):
                f[f"/{k}"] = E[k][i, :].astype(np.float32)


def read_precip(fn: Path) -> T.Dict[str, T.Any]:

    # with h5py.File(path / "simsize.h5", "r") as f:
    #     dat["llon"] = f["/llon"][()]
    #     dat["llat"] = f["/llat"][()]

    if h5py is None:
        raise ImportError("pip install h5py")

    with h5py.File(fn.with_name("simgrid.h5"), "r") as f:
        dat = {"mlon": f["/mlon"][:], "mlat": f["/mlat"][:]}

    with h5py.File(fn, "r") as f:
        for k in ("Q", "E0"):
            dat[k] = f[f"/{k}p"][:]

    return dat


def write_precip(outdir: Path, precip: T.Dict[str, T.Any]):

    if h5py is None:
        raise ImportError("pip install h5py")

    with h5py.File(outdir / "simsize.h5", "w") as f:
        f["/llon"] = precip["llon"]
        f["/llat"] = precip["llat"]

    with h5py.File(outdir / "simgrid.h5", "w") as f:
        f["/mlon"] = precip["mlon"].astype(np.float32)
        f["/mlat"] = precip["mlat"].astype(np.float32)

    for i, t in enumerate(precip["time"]):
        fn = outdir / (datetime2ymd_hourdec(t) + ".h5")

        with h5py.File(fn, "w") as f:
            for k in ("Q", "E0"):
                f.create_dataset(
                    f"/{k}p",
                    data=precip[k][i, :, :].transpose(),
                    dtype=np.float32,
                    compression="gzip",
                    compression_opts=1,
                    shuffle=True,
                    fletcher32=True,
                )


def loadframe3d_curvne(fn: Path) -> T.Dict[str, T.Any]:
    """
    just Ne
    """

    if h5py is None:
        raise ImportError("pip install h5py")

    with h5py.File(fn, "r") as f:
        dat = {"ne": (("x1", "x2", "x3"), f["/ne"][:])}

    return dat


def loadframe3d_curv(fn: Path) -> T.Dict[str, T.Any]:
    """
    curvilinear
    """

    #    grid = readgrid(fn.parent / "inputs/simgrid.h5")
    #    dat = xarray.Dataset(
    #        coords={"x1": grid["x1"][2:-2], "x2": grid["x2"][2:-2], "x3": grid["x3"][2:-2]}
    #    )

    if h5py is None:
        raise ImportError("pip install h5py")

    lxs = get_simsize(fn.parent / "inputs/simsize.h5")

    dat: T.Dict[str, T.Any] = {}

    with h5py.File(fn, "r") as f:
        dat["time"] = ymdhourdec2datetime(
            f["time/ymd"][0], f["time/ymd"][1], f["time/ymd"][2], f["time/UThour"][()]
        )

        if lxs[2] == 1:  # east-west
            p4 = (0, 3, 1, 2)
            p3 = (2, 0, 1)
        else:  # 3D or north-south, no swap
            p4 = (0, 3, 2, 1)
            p3 = (2, 1, 0)

        ns = f["/nsall"][:].transpose(p4)
        # np.any() in case neither is an np.ndarray
        if ns.shape[0] != LSP or np.any(ns.shape[1:] != lxs):
            raise ValueError(
                f"may have wrong permutation on read. lxs: {lxs}  ns x1,x2,x3: {ns.shape}"
            )

        dat["ns"] = (("lsp", "x1", "x2", "x3"), ns)
        vs = f["/vs1all"][:].transpose(p4)
        dat["vs"] = (("lsp", "x1", "x2", "x3"), vs)
        Ts = f["/Tsall"][:].transpose(p4)
        dat["Ts"] = (("lsp", "x1", "x2", "x3"), Ts)

        dat["ne"] = (("x1", "x2", "x3"), ns[LSP - 1, :, :, :])

        dat["v1"] = (
            ("x1", "x2", "x3"),
            (ns[:6, :, :, :] * vs[:6, :, :, :]).sum(axis=0) / dat["ne"][1],
        )

        dat["Ti"] = (
            ("x1", "x2", "x3"),
            (ns[:6, :, :, :] * Ts[:6, :, :, :]).sum(axis=0) / dat["ne"][1],
        )
        dat["Te"] = (("x1", "x2", "x3"), Ts[LSP - 1, :, :, :])

        dat["J1"] = (("x1", "x2", "x3"), f["/J1all"][:].transpose(p3))
        # np.any() in case neither is an np.ndarray
        if np.any(dat["J1"][1].shape != lxs):
            raise ValueError("may have wrong permutation on read")
        dat["J2"] = (("x1", "x2", "x3"), f["/J2all"][:].transpose(p3))
        dat["J3"] = (("x1", "x2", "x3"), f["/J3all"][:].transpose(p3))

        dat["v2"] = (("x1", "x2", "x3"), f["/v2avgall"][:].transpose(p3))
        dat["v3"] = (("x1", "x2", "x3"), f["/v3avgall"][:].transpose(p3))

        dat["Phitop"] = (("x2", "x3"), f["/Phiall"][:].transpose())

    return dat


def loadframe3d_curvavg(fn: Path) -> T.Dict[str, T.Any]:
    """
    end users should normally use loadframe() instead

    Parameters
    ----------
    fn: pathlib.Path
        filename of this timestep of simulation output
    """
    #    grid = readgrid(fn.parent / "inputs/simgrid.h5")
    #    dat = xarray.Dataset(
    #        coords={"x1": grid["x1"][2:-2], "x2": grid["x2"][2:-2], "x3": grid["x3"][2:-2]}
    #    )

    if h5py is None:
        raise ImportError("pip install h5py")

    lxs = get_simsize(fn.parent / "inputs/simsize.h5")

    dat: T.Dict[str, T.Any] = {}

    with h5py.File(fn, "r") as f:
        dat["time"] = ymdhourdec2datetime(
            f["time/ymd"][0], f["time/ymd"][1], f["time/ymd"][2], f["/time/UThour"][()]
        )

        p3 = (2, 0, 1)

        for j, k in zip(
            ("ne", "v1", "Ti", "Te", "J1", "J2", "J3", "v2", "v3"),
            (
                "neall",
                "v1avgall",
                "Tavgall",
                "TEall",
                "J1all",
                "J2all",
                "J3all",
                "v2avgall",
                "v3avgall",
            ),
        ):

            dat[j] = (("x1", "x2", "x3"), f[f"/{k}"][:].transpose(p3))

            if dat[j][1].shape != lxs:
                raise ValueError(f"simsize {lxs} does not match {k} {j} shape {dat[j][1].shape}")

        dat["Phitop"] = (("x2", "x3"), f["/Phiall"][:])

    return dat


def loadglow_aurmap(fn: Path) -> T.Dict[str, T.Any]:
    """
    read the auroral output from GLOW

    Parameters
    ----------
    fn: pathlib.Path
        filename of this timestep of simulation output
    """

    if h5py is None:
        raise ImportError("pip install h5py")

    with h5py.File(fn, "r") as h:
        dat = {"rayleighs": (("wavelength", "x2", "x3"), h["/aurora/iverout"][:])}

    return dat
