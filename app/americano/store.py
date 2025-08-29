from __future__ import annotations
import os, json
from os import PathLike
from dataclasses import dataclass
from typing import List
from .engine import Americano

@dataclass
class Tournament:
    id: str
    name: str
    americano: Americano

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "americano": self.americano.to_dict()}

    @staticmethod
    def from_dict(d: dict) -> "Tournament":
        return Tournament(id=d["id"], name=d["name"], americano=Americano.from_dict(d["americano"]))

class Store:
    def __init__(self, root: str | PathLike[str] = "data"):
        # accept Path or str; keep filesystem ops happy
        self.root = os.fspath(root)
        os.makedirs(self.root, exist_ok=True)

    def _file(self, tid: str) -> str:
        return os.path.join(self.root, f"{tid}.json")

    def save(self, t: Tournament) -> None:
        with open(self._file(t.id), "w", encoding="utf-8") as f:
            json.dump(t.to_dict(), f, indent=2, ensure_ascii=False)

    def load(self, tid: str) -> Tournament:
        path = self._file(tid)
        if not os.path.exists(path):
            raise FileNotFoundError("Tournament not found")
        with open(path, "r", encoding="utf-8") as f:
            return Tournament.from_dict(json.load(f))

    def list(self) -> List[dict]:
        out = []
        for fn in os.listdir(self.root):
            if not fn.endswith('.json'): continue
            with open(os.path.join(self.root, fn), "r", encoding="utf-8") as f:
                d = json.load(f)
                out.append({"id": d["id"], "name": d["name"]})
        return sorted(out, key=lambda x: x["name"].lower())