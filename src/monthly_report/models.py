from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class Message:
    date: datetime
    platform: str
    internal_name: str
    name: str
    user_id: str
    message: str

    def to_record(self) -> dict[str, object]:
        return {
            "date": self.date,
            "platform": self.platform,
            "internal_name": self.internal_name,
            "name": self.name,
            "id": self.user_id,
            "message": self.message,
        }
