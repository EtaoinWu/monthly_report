"""Exercise the notebook's plotting cells with synthetic data and small wordclouds."""

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from wordcloud import WordCloud

from monthly_report.analysis import build_message_dataframe
from monthly_report.models import Message

NOTEBOOK = Path(__file__).resolve().parents[1] / "Group Info Scan.ipynb"


class NotebookTests(unittest.TestCase):
    def test_pagination_colors_and_empty_clouds(self):
        notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
        state = {}

        def run(index):
            source = "".join(notebook["cells"][index]["source"])
            exec(compile(source, f"notebook-cell-{index}", "exec"), state)

        run(1)
        date = datetime.now().replace(day=1, hour=12, minute=0, second=0, microsecond=0)
        messages = [
            Message(date, "qqv2", f"Person {i}", f"Person {i}", str(i), "hello statistics world")
            for i in range(40)
        ]
        frame = build_message_dataframe(messages)
        state.update(
            df=frame,
            messages=messages,
            RECENT_CUTOFF=datetime(2025, 1, 1),
            OLD_CUTOFF=datetime(2025, 1, 1),
            TOP_N=16,
            INDIVIDUAL_CLOUD_PAGES=3,
            INDIVIDUAL_CLOUD_ROWS=4,
            INDIVIDUAL_CLOUD_COLUMNS=4,
            INDIVIDUAL_CLOUD_SINCE=None,
            font_path=font_manager.findfont("DejaVu Sans"),
        )
        state["INDIVIDUAL_COLORS"].update(state["individual_colors"](frame["name"].to_list()))
        original_colors = state["INDIVIDUAL_COLORS"].copy()

        def small_cloud(**kwargs):
            kwargs.update(width=100, height=100, max_words=5, max_font_size=20, scale=1)
            return WordCloud(**kwargs)

        try:
            with tempfile.TemporaryDirectory() as directory, patch.object(plt, "show"):
                state["BASE_DIR"] = Path(directory)
                for index in [5, 6, 7, 8, 9, 10, 11]:
                    run(index)
                state["WordCloud"] = small_cloud
                for index in [12, 13]:
                    run(index)
                plt.close("all")
                run(14)
                figures = [plt.figure(i) for i in plt.get_fignums()]
                self.assertEqual(len(figures), 3)
                self.assertEqual(
                    [sum(bool(ax.get_title()) for ax in fig.axes) for fig in figures], [16, 16, 8]
                )
                titles = [ax.get_title() for fig in figures for ax in fig.axes if ax.get_title()]
                self.assertEqual(len(set(titles)), 40)
                self.assertEqual(state["INDIVIDUAL_COLORS"], original_colors)
                for words in [[], ["the and or"], ["[图片]"]]:
                    import polars as pl

                    self.assertIsNone(state["make_wordcloud"](pl.Series(words, dtype=pl.String)))
        finally:
            plt.close("all")


if __name__ == "__main__":
    unittest.main()
