import re
from collections.abc import Iterable, Iterator, Sequence
from datetime import datetime
from itertools import tee, zip_longest
from zoneinfo import ZoneInfo

import emoji
import orjson

from monthly_report.models import Message

QQ_HEADER_PATTERN = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{1,2}:\d{1,2}:\d{1,2}) (.+?)(\(\d+\)|<.+>)$",
    re.MULTILINE,
)


def pairwise(
    iterable: Sequence[re.Match[str]],
) -> Iterator[tuple[re.Match[str], re.Match[str] | None]]:
    left, right = tee(iterable)
    next(right, None)
    return zip_longest(left, right)


def strip_leading_mentions(text: str) -> str:
    stripped = text.strip()
    if not stripped or not stripped.startswith("@"):
        return stripped
    split_at = stripped.find(" ")
    if split_at == -1:
        return stripped
    return strip_leading_mentions(stripped[split_at + 1 :])


def parse_qq_messages(
    raw_text: str,
    *,
    namemap: dict[str, str],
    erased_ids: set[str],
    id_prefix: str = "q",
) -> list[Message]:
    matches = list(QQ_HEADER_PATTERN.finditer(raw_text))
    parsed: list[Message] = []

    for match, next_match in pairwise(matches):
        user_id = f"{id_prefix}{match.group(3)}"
        if user_id in erased_ids:
            continue

        start = match.end()
        end = next_match.start() if next_match else len(raw_text)
        content = raw_text[start:end].strip("\r\n")
        parsed.append(
            Message(
                date=datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S"),
                platform="qq",
                internal_name=match.group(2),
                name=namemap.get(user_id, "not found"),
                user_id=user_id,
                message=strip_leading_mentions(content),
            )
        )
    return parsed


def normalize_tg_text(text: str | list[str | dict[str, str]]) -> str:
    if isinstance(text, str):
        return text
    out: list[str] = []
    for chunk in text:
        if isinstance(chunk, str):
            out.append(chunk)
        else:
            out.append(chunk.get("text", ""))
    return "".join(out)


def prettify_name(name: str | None) -> str:
    if name is None:
        return "Deleted Account"

    cleaned = re.sub(r"[\x00-\x1f]|[\x81\x8d\x8f\x90\x9d\xa0\u200C\u2060\uFEFF]", "", name)
    split_pos = len(cleaned)
    for splitter in {"|", "丨"}:
        first_pos = cleaned.find(splitter)
        if first_pos != -1:
            split_pos = min(split_pos, first_pos)
    return emoji.demojize(cleaned[:split_pos])


def parse_tg_messages(
    raw_json: str | bytes,
    *,
    namemap: dict[str, str],
    erased_ids: set[str],
    id_prefix: str = "t",
    report_timezone: str = "Asia/Shanghai",
) -> list[Message]:
    data = orjson.loads(raw_json)
    messages: Iterable[dict[str, object]] = data.get("messages", [])
    parsed: list[Message] = []

    for entry in messages:
        entry_type = str(entry.get("type", ""))
        from_id = str(entry.get("from_id", ""))
        if (
            entry_type != "message"
            or from_id in erased_ids
            or f"{id_prefix}{from_id}" in erased_ids
        ):
            continue

        user_id = f"{id_prefix}{from_id}"
        from_name_raw = entry.get("from")
        from_name = from_name_raw if isinstance(from_name_raw, str) else None

        text_raw = entry.get("text", "")
        if isinstance(text_raw, str):
            text_value: str | list[str | dict[str, str]] = text_raw
        elif isinstance(text_raw, list):
            text_value = [
                chunk
                for chunk in text_raw
                if isinstance(chunk, str)
                or (isinstance(chunk, dict) and isinstance(chunk.get("text"), str))
            ]
        else:
            text_value = ""

        parsed.append(
            Message(
                date=local_datetime(str(entry["date"]), report_timezone),
                platform="tg",
                internal_name=prettify_name(from_name),
                name=namemap.get(user_id, "not found"),
                user_id=user_id,
                message=normalize_tg_text(text_value),
            )
        )

    return parsed


def hydrate_names(messages: list[Message], namemap: dict[str, str]) -> None:
    guessed = {
        msg.user_id: (
            msg.internal_name
            if msg.platform in {"qq", "qqv2"}
            else prettify_name(msg.internal_name)
        )
        for msg in messages
        if msg.name == "not found"
    }
    for msg in messages:
        msg.name = namemap.get(msg.user_id, guessed.get(msg.user_id, msg.user_id))


def local_datetime(value: str, report_timezone: str) -> datetime:
    """Keep legacy naive export dates; convert offset-aware dates into report time."""
    date = datetime.fromisoformat(value)
    if date.tzinfo is not None:
        date = date.astimezone(ZoneInfo(report_timezone)).replace(tzinfo=None)
    return date


def parse_qqv2_messages(
    raw_json: str | bytes,
    *,
    namemap: dict[str, str],
    erased_ids: set[str],
    id_prefix: str = "q",
    report_timezone: str = "Asia/Shanghai",
) -> list[Message]:
    """Map QQChatExporter records to legacy QQ identities, without expanding forwards."""
    parsed: list[Message] = []
    for entry in orjson.loads(raw_json).get("messages", []):
        if entry.get("system") or entry.get("type") == "system":
            continue
        sender = entry.get("sender", {})
        uin = sender.get("uin")
        # UID fallback must never collide with numeric legacy QQ IDs.
        user_id = f"{id_prefix}({uin})" if uin else f"{id_prefix}uid:{sender['uid']}"
        if user_id in erased_ids:
            continue
        internal_name = sender.get("groupCard") or sender.get("name") or sender.get("nickname")
        parsed.append(
            Message(
                date=local_datetime(entry["time"], report_timezone),
                platform="qqv2",
                internal_name=internal_name or user_id,
                name=namemap.get(user_id, "not found"),
                user_id=user_id,
                message=strip_leading_mentions(entry.get("content", {}).get("text", "")),
            )
        )
    return parsed
