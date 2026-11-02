"""Rust-backed Chinese segmentation, with support for existing Jieba user dictionaries."""

from pathlib import Path

import polars as pl
import rjieba


def load_userdict(path: Path) -> None:
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        fields = line.split()
        if not fields:
            continue
        word = fields[0]
        freq = int(fields[1]) if len(fields) > 1 and fields[1].isdigit() else None
        tag = fields[-1] if len(fields) > 1 and not fields[-1].isdigit() else None
        rjieba.add_word(word, freq if freq is not None else rjieba.suggest_freq(word), tag)


def split_words(messages: pl.Series) -> str:
    text = "\n".join(messages.drop_nulls().to_list()).replace("A 宝", "A宝")
    return " ".join(rjieba.cut(text)).strip()
