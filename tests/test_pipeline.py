import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import polars as pl

from monthly_report.analysis import (
    build_message_dataframe,
    grouped_message_counts,
    monthly_platform_counts,
    top_n_with_other,
)
from monthly_report.config import ReportConfig
from monthly_report.loaders import load_all_messages
from monthly_report.models import Message
from monthly_report.parsers import parse_qq_messages, parse_qqv2_messages, parse_tg_messages
from monthly_report.text import load_userdict, split_words
from monthly_report.visualization import individual_colors, recent_months


def qqv2_entry(**overrides):
    entry = {
        "time": "2026-10-31T18:30:00.000Z",
        "sender": {"uin": "123", "uid": "u_abc", "name": "Nick", "groupCard": "Card"},
        "type": "text",
        "system": False,
        "content": {"text": "@Someone hello", "elements": []},
    }
    return entry | overrides


class PipelineTests(unittest.TestCase):
    def test_qqv2_identity_time_text_and_service_filter(self):
        raw = json.dumps(
            {"messages": [qqv2_entry(), qqv2_entry(system=True), qqv2_entry(type="system")]}
        )
        messages = parse_qqv2_messages(raw, namemap={"q(123)": "Canonical"}, erased_ids=set())
        self.assertEqual(len(messages), 1)
        msg = messages[0]
        self.assertEqual(
            (msg.user_id, msg.name, msg.internal_name), ("q(123)", "Canonical", "Card")
        )
        self.assertEqual(msg.date, datetime(2026, 11, 1, 2, 30))
        self.assertEqual((msg.platform, msg.message), ("qqv2", "hello"))
        self.assertEqual(parse_qqv2_messages(raw, namemap={}, erased_ids={"q(123)"}), [])

    def test_forward_and_reply_count_once_without_expanding(self):
        for kind in ["forward", "reply", "image"]:
            raw = json.dumps(
                {
                    "messages": [
                        qqv2_entry(
                            type=kind,
                            content={
                                "text": "Body [image]",
                                "elements": [{"messages": [qqv2_entry()]}],
                            },
                        )
                    ]
                }
            )
            messages = parse_qqv2_messages(raw, namemap={}, erased_ids=set())
            self.assertEqual(len(messages), 1)
            self.assertEqual(messages[0].message, "Body [image]")

    def test_missing_numeric_id_has_distinct_fallback(self):
        raw = json.dumps({"messages": [qqv2_entry(sender={"uid": "abc"})]})
        msg = parse_qqv2_messages(raw, namemap={}, erased_ids=set())[0]
        self.assertEqual(msg.user_id, "quid:abc")

    def test_qq_preserves_last_characters_and_unpadded_time(self):
        for ending in ["", "\n", "\r\n\r\n"]:
            raw = "2026-10-31 1:2:3 Nick(123)\nhello" + ending
            msg = parse_qq_messages(raw, namemap={}, erased_ids=set())[0]
            self.assertEqual(msg.message, "hello")
            self.assertEqual(msg.date, datetime(2026, 10, 31, 1, 2, 3))

    def test_tg_erasure_and_rich_text(self):
        entry = {
            "type": "message",
            "from_id": "user123",
            "from": "Nick",
            "date": "2026-10-31T18:30:00+00:00",
            "text": ["hello ", {"text": "world"}],
        }
        raw = json.dumps({"messages": [entry]})
        msg = parse_tg_messages(raw, namemap={}, erased_ids=set())[0]
        self.assertEqual(msg.message, "hello world")
        self.assertEqual(msg.date, datetime(2026, 11, 1, 2, 30))
        for erased in [{"user123"}, {"tuser123"}]:
            self.assertEqual(parse_tg_messages(raw, namemap={}, erased_ids=erased), [])

    def test_loader_routes_json_and_merges_qq_identities(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            names = root / "names.map"
            names.write_text(json.dumps({"q(123)": "Canonical"}), encoding="utf-8")
            (root / "old.txt").write_text("2026-10-01 1:2:3 Old(123)\nhello", encoding="utf-8")
            (root / "new.qq.json").write_text(json.dumps({"messages": [qqv2_entry()]}))
            (root / "telegram.json").write_text(
                json.dumps(
                    {
                        "messages": [
                            {
                                "type": "message",
                                "from_id": "user456",
                                "from": "TG",
                                "date": "2026-10-15T00:00:00",
                                "text": "hi",
                            }
                        ]
                    }
                )
            )
            messages = load_all_messages(ReportConfig(base_dir=root, namemap_file=names))
            self.assertEqual([m.platform for m in messages], ["qq", "tg", "qqv2"])
            self.assertEqual(
                [m.name for m in messages if m.user_id == "q(123)"], ["Canonical", "Canonical"]
            )

    def test_polars_aggregation_calendar_gaps_and_cutoff(self):
        messages = [
            Message(datetime(2026, month, day), platform, name, name, name, "hi")
            for month, day, platform, name in [
                (1, 1, "qq", "A"),
                (1, 2, "qq", "B"),
                (3, 1, "qqv2", "A"),
                (3, 2, "tg", "C"),
            ]
        ]
        frame = build_message_dataframe(messages)
        self.assertIsInstance(frame, pl.DataFrame)
        counts = grouped_message_counts(frame)
        self.assertEqual(counts.rows(), [("A", 2), ("B", 1), ("C", 1)])
        self.assertEqual(top_n_with_other(counts, 1).rows(), [("A", 2), ("Other", 2)])
        self.assertEqual(
            grouped_message_counts(frame, since=datetime(2026, 3, 1)).rows(), [("C", 1)]
        )
        monthly = monthly_platform_counts(frame)
        self.assertEqual(monthly["month"].to_list(), ["2026-01", "2026-02", "2026-03"])
        self.assertEqual(monthly.row(1), ("2026-02", 0, 0, 0))
        self.assertEqual(sum(monthly.select(pl.sum_horizontal(pl.exclude("month"))).to_series()), 4)

    def test_empty_data_and_invalid_top(self):
        frame = build_message_dataframe([])
        counts = grouped_message_counts(frame)
        self.assertTrue(counts.is_empty())
        self.assertTrue(top_n_with_other(counts, 3).is_empty())
        self.assertEqual(monthly_platform_counts(frame).columns, ["month"])
        with self.assertRaises(ValueError):
            top_n_with_other(counts, 0)

    def test_colors_and_month_rollover(self):
        colors = individual_colors(["A", "B", "C", "A"])
        self.assertEqual(set(colors), {"A", "B", "C", "Other"})
        self.assertEqual(len(set(colors.values())), 4)
        self.assertEqual([colors[name] for name in ["B", "A"]], [colors["B"], colors["A"]])
        months, include_current = recent_months(datetime(2026, 1, 1))
        self.assertFalse(include_current)
        self.assertEqual((months[0], months[-1]), (datetime(2025, 4, 1), datetime(2025, 12, 1)))
        self.assertTrue(recent_months(datetime(2026, 1, 16))[1])

    def test_custom_dictionary_and_empty_text(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dict.txt"
            path.write_text("月报测试专用词 100000 nz\n月报另一个词\n", encoding="utf-8-sig")
            load_userdict(path)
            self.assertIn("月报测试专用词", split_words(pl.Series(["月报测试专用词"])).split())
        self.assertEqual(split_words(pl.Series([], dtype=pl.String)), "")


if __name__ == "__main__":
    unittest.main()
