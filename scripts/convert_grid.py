#!/usr/bin/env python3
"""
convert Gemini grid to HDF5 .h5
"""

from pathlib import Path
import argparse

import gemini3d.read as read
import gemini3d.write as write


def cli():
    p = argparse.ArgumentParser()
    p.add_argument("format", help="file format", choices=["h5", "nc"])
    p.add_argument("indir", help="Gemini simgrid.dat")
    p.add_argument("-i", "--intype", help="type of input file [.dat]", default=".dat")
    p.add_argument("-o", "--outdir", help="directory to write HDF5 files")
    P = p.parse_args()

    infile = Path(P.indir).expanduser()
    if P.outdir:
        outdir = Path(P.outdir).expanduser()
    elif infile.is_file():
        outdir = infile.parent
    else:
        raise FileNotFoundError(infile)

    suffix = f".{P.format}"

    outfile = outdir / (infile.stem + suffix)
    print(infile, "=>", outfile)

    xg = read.grid(infile, file_format=P.intype)

    cfg = {
        "indat_size": infile.with_name(f"simsize{suffix}"),
        "indat_grid": infile.with_suffix(suffix),
    }

    write.grid(cfg, file_format=P.format, xg=xg)


if __name__ == "__main__":
    cli()
