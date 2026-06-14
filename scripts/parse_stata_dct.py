"""Utilities for reading NSFG fixed-width files using official Stata .dct files."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


DCT_RE = re.compile(
    r"_column\((?P<start>\d+)\)\s+\S+\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s+%(?P<width>\d+)",
    re.IGNORECASE,
)


def parse_dct(dct_path: Path) -> pd.DataFrame:
    rows = []
    for line in dct_path.read_text(encoding="latin1").splitlines():
        match = DCT_RE.search(line)
        if not match:
            continue
        start = int(match.group("start"))
        width = int(match.group("width"))
        rows.append(
            {
                "name": match.group("name").lower(),
                "start": start,
                "width": width,
                "end": start + width - 1,
            }
        )
    if not rows:
        raise ValueError(f"No Stata dictionary columns parsed from {dct_path}")
    return pd.DataFrame(rows)


def read_fwf_with_dct(dat_path: Path, dct_path: Path, usecols: list[str] | None = None) -> pd.DataFrame:
    spec = parse_dct(dct_path)
    if usecols is not None:
        wanted = {c.lower() for c in usecols}
        spec = spec[spec["name"].isin(wanted)].copy()
    colspecs = [(int(row.start) - 1, int(row.end)) for row in spec.itertuples(index=False)]
    df = pd.read_fwf(
        dat_path,
        colspecs=colspecs,
        names=spec["name"].tolist(),
        dtype="string",
        na_values=["", " ", "."],
        keep_default_na=True,
    )
    return df
