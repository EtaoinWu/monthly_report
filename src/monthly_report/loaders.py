import json
from pathlib import Path

from monthly_report.config import ReportConfig
from monthly_report.models import Message
from monthly_report.parsers import hydrate_names, parse_qq_messages, parse_tg_messages


def load_namemap(path: Path) -> dict[str, str]:
    with path.open("r", encoding="utf-8") as file:
        return dict(json.load(file))


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
    for file_path in sorted(config.base_dir.glob(config.tg_pattern)):
        raw_json = file_path.read_text(encoding="utf-8")
        tg_messages.extend(
            parse_tg_messages(
                raw_json,
                namemap=namemap,
                erased_ids=config.erased_ids,
                id_prefix=config.tg_prefix,
            )
        )

    all_messages = sorted([*qq_messages, *tg_messages], key=lambda msg: msg.date)
    hydrate_names(all_messages, namemap)
    return all_messages
