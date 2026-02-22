from datetime import datetime
from typing import cast

import pandas as pd

from monthly_report.models import Message


def build_message_dataframe(messages: list[Message]) -> pd.DataFrame:
    frame = pd.DataFrame.from_records(msg.to_record() for msg in messages)
    frame["msg_len"] = 1
    return frame.sort_values("date").reset_index(drop=True)


def grouped_message_counts(frame: pd.DataFrame, *, since: datetime | None = None) -> pd.Series:
    filtered = frame if since is None else frame[frame["date"] > since]
    grouped = filtered.groupby("name")["msg_len"].sum().sort_values(ascending=False)
    return grouped


def top_n_with_other(counts: pd.Series, n_top: int) -> pd.Series:
    top = counts.iloc[:n_top]
    other_sum = counts.iloc[n_top:].sum()
    if other_sum == 0:
        return top
    other = pd.Series(index=["Other"], data=[other_sum], name=counts.name)
    return cast(pd.Series, pd.concat([top, other]))


def monthly_platform_counts(frame: pd.DataFrame, *, since: datetime | None = None) -> pd.DataFrame:
    filtered = frame if since is None else frame[frame["date"] > since]
    grouped = (
        filtered.groupby([pd.Grouper(key="date", freq="ME"), "platform"])["msg_len"]
        .sum()
        .unstack(fill_value=0)
    )
    datetime_index = cast(pd.DatetimeIndex, grouped.index)
    grouped.index = datetime_index.strftime("%Y-%m")
    return grouped
