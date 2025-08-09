from typing import Any, Dict, List, Optional, Tuple
import re
from databases.db_engine import SQLiteDB

PREFIXES = (
    "StaffName_Forename_Male_",
    "StaffName_Forename_Female_",
    "StaffName_Surname_",
)


def _strip_brackets(s: str) -> str:
    if not s:
        return s
    if s.startswith("[") and s.endswith("]"):
        return s[1:-1]
    return s


def _remove_prefix(s: str) -> str:
    for p in PREFIXES:
        if s.startswith(p):
            return s[len(p):]
    return s


def _token_to_name(s: str) -> str:
    s = _strip_brackets(s or "")
    s = _remove_prefix(s)
    s = s.replace("_", " ").strip()
    return s


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower().strip())


def load_clean_staff(db: SQLiteDB) -> List[Dict[str, Any]]:
    rows = db.execute("SELECT StaffID, FirstName, LastName FROM Staff_BasicData;")
    out: List[Dict[str, Any]] = []
    for r in rows:
        first = _token_to_name(r["FirstName"])
        last  = _token_to_name(r["LastName"])
        out.append({
            "StaffID": r["StaffID"],
            "first": first,
            "last": last,
            "full": f"{first} {last}".strip(),
            "first_norm": _norm(first),
            "last_norm": _norm(last),
            "full_norm": _norm(f"{first} {last}"),
        })
    return out


def find_staff_id_by_name(db: SQLiteDB, full_name: str) -> Tuple[Optional[int], List[Dict[str, Any]]]:
    people = load_clean_staff(db)
    q = _norm(full_name)

    exact = [p for p in people if p["full_norm"] == q]
    if len(exact) == 1:
        return exact[0]["StaffID"], exact

    starts = [p for p in people if p["full_norm"].startswith(q)]
    if len(starts) == 1:
        return starts[0]["StaffID"], starts

    parts = q.split(" ")
    if len(parts) == 2:
        f, l = parts
        fl = [p for p in people if p["first_norm"] == f and p["last_norm"] == l]
        if len(fl) == 1:
            return fl[0]["StaffID"], fl

    partials = [p for p in people if q in p["full_norm"]]
    if len(partials) == 1:
        return partials[0]["StaffID"], partials

    return None, (exact or starts or partials)


if __name__ == "__main__":
    db = SQLiteDB("../main.db")
    db.connect()

    target_name = "Lewis Hamilton"
    staff_id, candidates = find_staff_id_by_name(db, target_name)

    if staff_id is not None:
        print(f"Match: {target_name} -> StaffID {staff_id}")
    else:
        print(f"No exact match found for '{target_name}'")

    db.close()
