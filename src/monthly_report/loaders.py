from pathlib import Path

import orjson

from monthly_report.config import ReportConfig
from monthly_report.models import Message
from monthly_report.parsers import (
    hydrate_names,
    parse_qq_messages,
    parse_qqv2_messages,
    parse_tg_messages,
)


def load_namemap(path: Path) -> dict[str, str]:
    return dict(orjson.loads(path.read_bytes()))


def load_all_messages(config: ReportConfig) -> list[Message]:
    namemap = load_namemap(config.namemap_file)

    qq_messages: list[Message] = []
    for file_path in sorted(config.base_dir.glob(config.qq_pattern)):
        raw_text = file_path.read_text(encoding="utf-8")
        qq_messages.extend(
            parse_qq_messages(
                raw_text,
                namemap=namemap,
                erased_ids=config.erased_ids,
                id_prefix=config.qq_prefix,
            )
        )

    tg_messages: list[Message] = []
    qqv2_files = set(config.base_dir.glob(config.qqv2_pattern))
    qqv2_messages: list[Message] = []
    for file_path in sorted(qqv2_files):
        qqv2_messages.extend(
            parse_qqv2_messages(
                file_path.read_bytes(),
                namemap=namemap,
                erased_ids=config.erased_ids,
                id_prefix=config.qq_prefix,
                report_timezone=config.report_timezone,
            )
        )

    for file_path in sorted(config.base_dir.glob(config.tg_pattern)):
        if file_path in qqv2_files:
            continue
        raw_json = file_path.read_bytes()
        tg_messages.extend(
            parse_tg_messages(
                raw_json,
                namemap=namemap,
                erased_ids=config.erased_ids,
                id_prefix=config.tg_prefix,
                report_timezone=config.report_timezone,
            )
        )

    all_messages = sorted([*qq_messages, *qqv2_messages, *tg_messages], key=lambda msg: msg.date)
    hydrate_names(all_messages, namemap)
    return all_messages
