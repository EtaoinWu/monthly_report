"""Small plotting helpers shared by the report notebooks."""

import calendar
import colorsys
from datetime import datetime

import numpy as np
import polars as pl


def individual_colors(names: list[str]) -> dict[str, str]:
    """Shuffle an evenly spaced, bright pastel palette once for a report session."""
    names = sorted(set(names) - {"Other"})
    rng = np.random.default_rng()
    offset = rng.random()
    hues = (np.arange(len(names)) / max(1, len(names)) + offset) % 1
    rng.shuffle(hues)
    colors = {}
    for name, hue in zip(names, hues, strict=True):
        red, green, blue = colorsys.hls_to_rgb(float(hue), 0.72, 0.66)
        colors[name] = f"#{round(red * 255):02x}{round(green * 255):02x}{round(blue * 255):02x}"
    colors["Other"] = "#8892a6"
    return colors


def recent_months(today: datetime, count: int = 9) -> tuple[list[datetime], bool]:
    include_current = today.day > calendar.monthrange(today.year, today.month)[1] / 2
    end = today.year * 12 + today.month - 1 - (not include_current)
    months = [datetime(index // 12, index % 12 + 1, 1) for index in range(end - count + 1, end + 1)]
    return months, include_current


def month_messages(frame: pl.DataFrame, month: datetime) -> pl.DataFrame:
    return frame.filter(pl.col("date").dt.truncate("1mo") == month)
