from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True, frozen=True)
class ReportConfig:
    base_dir: Path
    namemap_file: Path = Path("namemap.json")
    qq_pattern: str = "*.txt"
    tg_pattern: str = "*.json"
    qqv2_pattern: str = "*.qq.json"
    report_timezone: str = "Asia/Shanghai"
    qq_prefix: str = "q"
    tg_prefix: str = "t"
    erased_ids: set[str] = field(default_factory=set)
