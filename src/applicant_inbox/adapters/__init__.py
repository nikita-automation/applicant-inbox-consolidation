"""One module per channel. Adding a channel = one `parse(path) -> ParseResult` function and one line here."""

from typing import Callable, Dict

from ..models import ParseResult
from . import agency, board_a, board_b, chat, mail, webform

ADAPTERS: Dict[str, Callable[[str], ParseResult]] = {
    "webform": webform.parse,
    "board_a": board_a.parse,
    "board_b": board_b.parse,
    "agency": agency.parse,
    "chat": chat.parse,
    "mail": mail.parse,
}

# Where each adapter finds its data in a sample/export directory (used by `ingest-dir`).
DEFAULT_PATHS = {
    "webform": "webform.jsonl",
    "board_a": "board_a.csv",
    "board_b": "board_b.csv",
    "agency": "agency.json",
    "chat": "chat_export.txt",
    "mail": "mail",
}
