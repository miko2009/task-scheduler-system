import csv
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ItemRow = Dict[str, str]

_ITEMS_CACHE: Optional[List[ItemRow]] = None
_DEFAULT_PATH = Path(__file__).resolve().parent.parent / "items.csv"


def load_items(path: Optional[Path] = None) -> List[ItemRow]:
    """Load items.csv once and cache it."""
    global _ITEMS_CACHE
    if _ITEMS_CACHE is not None:
        return _ITEMS_CACHE
    target = path or _DEFAULT_PATH
    rows: List[ItemRow] = []
    with target.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    _ITEMS_CACHE = rows
    return rows


def _split_slot(internal_name: str) -> str:
    # Names look like "Head_Vlog_MessyBun"; slot is the first token.
    return internal_name.split("_", 1)[0]


def build_accessory_lookup(items: List[ItemRow]) -> Dict[str, List[ItemRow]]:
    grouped: Dict[str, List[ItemRow]] = {"Head": [], "Body": [], "Other": []}
    for row in items:
        slot = _split_slot(row["internal_name"])
        if slot in grouped:
            grouped[slot].append(row)
    return grouped


def pick_from_series(
    grouped: Dict[str, List[ItemRow]], set_series: Optional[str] = None
) -> Tuple[ItemRow, ItemRow, ItemRow]:
    """Pick a head/body/other trio. Prefer matching set_series if available."""
    def pick(slot: str) -> ItemRow:
        candidates = grouped.get(slot, [])
        if set_series:
            for row in candidates:
                if row.get("set_series") == set_series:
                    return row
        return candidates[0] if candidates else {"item_id": "unknown", "display_name": slot, "set_series": "unknown", "quality": "Common"}

    return pick("Head"), pick("Body"), pick("Other")


def select_accessory_set(
    preferred_series: Optional[str] = None, items_path: Optional[Path] = None
) -> Dict[str, Dict[str, str]]:
    """Return a simple head/body/other dict chosen from items.csv."""
    items = load_items(items_path)
    grouped = build_accessory_lookup(items)
    head, body, other = pick_from_series(grouped, preferred_series)

    def serialize(row: ItemRow, reason: str) -> Dict[str, str]:
        return {
            "item_id": row.get("item_id", "unknown"),
            "display_name": row.get("display_name", "Unknown"),
            "set_series": row.get("set_series", "unknown"),
            "quality": row.get("quality", "Common"),
            "reason": reason,
        }

    behavior_reason = f"Matched to set '{preferred_series}'" if preferred_series else "Default accessory set"
    return {
        "head": serialize(head, behavior_reason),
        "body": serialize(body, behavior_reason),
        "other": serialize(other, behavior_reason),
    }
