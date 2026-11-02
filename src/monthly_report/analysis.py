from datetime import datetime

import polars as pl

from monthly_report.models import Message

MESSAGE_SCHEMA = pl.Schema(
    {
        "date": pl.Datetime("us"),
        "platform": pl.String(),
        "internal_name": pl.String(),
        "name": pl.String(),
        "id": pl.String(),
        "message": pl.String(),
    }
)


def build_message_dataframe(messages: list[Message]) -> pl.DataFrame:
    return (
        pl.from_dicts((msg.to_record() for msg in messages), schema=MESSAGE_SCHEMA)
        .with_columns(pl.lit(1, dtype=pl.Int64).alias("msg_len"))
        .sort("date")
    )


def grouped_message_counts(frame: pl.DataFrame, *, since: datetime | None = None) -> pl.DataFrame:
    filtered = frame if since is None else frame.filter(pl.col("date") > since)
    return (
        filtered.group_by("name")
        .agg(pl.col("msg_len").sum())
        .sort(["msg_len", "name"], descending=[True, False])
    )


def top_n_with_other(counts: pl.DataFrame, n_top: int) -> pl.DataFrame:
    if n_top < 1:
        raise ValueError("n_top must be positive")
    top = counts.head(n_top)
    other_sum = counts.slice(n_top).get_column("msg_len").sum()
    if not other_sum:
        return top
    return pl.concat(
        [top, pl.DataFrame({"name": ["Other"], "msg_len": [other_sum]}, schema=counts.schema)]
    )


def monthly_platform_counts(frame: pl.DataFrame, *, since: datetime | None = None) -> pl.DataFrame:
    """Wide monthly counts, including zero-filled calendar gaps; month is YYYY-MM."""
    filtered = frame if since is None else frame.filter(pl.col("date") > since)
    if filtered.is_empty():
        return pl.DataFrame(schema={"month": pl.String})
    grouped = (
        filtered.with_columns(pl.col("date").dt.truncate("1mo").alias("month"))
        .group_by(["month", "platform"])
        .agg(pl.col("msg_len").sum())
        .pivot(on="platform", index="month", values="msg_len")
        .sort("month")
        .upsample(time_column="month", every="1mo")
        .with_columns(pl.exclude("month").fill_null(0))
        .with_columns(pl.col("month").dt.strftime("%Y-%m"))
    )
    return grouped.select("month", *sorted(c for c in grouped.columns if c != "month"))
