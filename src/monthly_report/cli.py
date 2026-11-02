import argparse
import json
from datetime import datetime
from pathlib import Path

from monthly_report.analysis import (
    build_message_dataframe,
    grouped_message_counts,
    monthly_platform_counts,
)
from monthly_report.config import ReportConfig
from monthly_report.loaders import load_all_messages


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load QQ/TG history and print key report tables")
    parser.add_argument(
        "--base-dir",
        type=Path,
        required=True,
        help="Directory containing exported chat files",
    )
    parser.add_argument(
        "--namemap",
        type=Path,
        default=Path("namemap.json"),
        help="Path to namemap.json",
    )
    parser.add_argument(
        "--since",
        type=str,
        default=None,
        help="Optional lower-bound date (YYYY-MM-DD)",
    )
    parser.add_argument("--top", type=int, default=16, help="Top N members to include")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cutoff = datetime.fromisoformat(args.since) if args.since else None
    config = ReportConfig(base_dir=args.base_dir, namemap_file=args.namemap)

    messages = load_all_messages(config)
    frame = build_message_dataframe(messages)

    counts = grouped_message_counts(frame, since=cutoff)
    platform = monthly_platform_counts(frame, since=cutoff)

    print(json.dumps({"message_count": len(messages), "members": int(counts.shape[0])}, indent=2))
    print("\nTop members:")
    print(counts.head(args.top))
    print("\nPlatform by month:")
    print(platform)


if __name__ == "__main__":
    main()
