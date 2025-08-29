from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import re

Player = str
Team = Tuple[Player, Player]

@dataclass
class Game:
    court: int
    teamA: Team
    teamB: Team
    scoreA: Optional[int] = None
    scoreB: Optional[int] = None

class Americano:
    def __init__(self, players: List[Player], courts: int = 1):
        if courts < 1:
            raise ValueError("courts must be >= 1")
        if len(players) < 4:
            raise ValueError("Need at least 4 players")
        self.players: List[Player] = players[:]
        self.courts: int = courts
        self.round_idx: int = 0
        # Stats
        self.matches_played: Dict[Player, int] = {p: 0 for p in players}
        self.games_for: Dict[Player, int] = {p: 0 for p in players}
        self.games_against: Dict[Player, int] = {p: 0 for p in players}
        self.points: Dict[Player, int] = {p: 0 for p in players}
        self.last_round: Dict[Player, int] = {p: -10 for p in players}
        # Relationship tracking
        self.partner_count: Dict[str, int] = {}
        self.partner_last_round: Dict[str, int] = {}
        self.opponent_count: Dict[str, int] = {}
        self.opponent_last_round: Dict[str, int] = {}
        # History
        self.rounds: List[List[Game]] = []

    # ---------- scheduling ----------
    def next_round(self) -> List[Game]:
        self.round_idx += 1
        sorted_players = sorted(
            self.players,
            key=lambda p: (self.matches_played[p], self.last_round[p], p.lower()),
        )
        selected: List[Player] = []
        games: List[Game] = []
        max_games = min(self.courts, (len(self.players) // 4))
        if max_games == 0:
            raise RuntimeError("Need at least 4 players to schedule a round.")

        def pick_four() -> Optional[List[Player]]:
            pool = [p for p in sorted_players if p not in selected]
            if len(pool) < 4:
                return None
            block = pool[:6] if len(pool) >= 6 else pool
            return block[:4]

        for c in range(1, max_games + 1):
            four = pick_four()
            if not four:
                break
            for p in four:
                selected.append(p)
            teamA, teamB = self._best_split_of_four(four)
            games.append(Game(court=c, teamA=teamA, teamB=teamB))

        for p in selected:
            self.last_round[p] = self.round_idx
        self.rounds.append(games)
        return games

    def _best_split_of_four(self, four: List[Player]) -> Tuple[Team, Team]:
        assert len(four) == 4
        a, b, c, d = four
        splits = [((a, b), (c, d)), ((a, c), (b, d)), ((a, d), (b, c))]
        best = None
        best_score = float('inf')
        for t1, t2 in splits:
            s = self._split_score(t1, t2)
            if s < best_score:
                best_score = s
                best = (self._ordered_team(t1), self._ordered_team(t2))
        return best  # type: ignore

    def _ordered_team(self, t: Team) -> Team:
        p, q = t
        return (p, q) if p <= q else (q, p)

    def _pair_key(self, p: Player, q: Player) -> str:
        a, b = sorted([p, q])
        return f"{a}|{b}"

    def _split_score(self, t1: Team, t2: Team) -> float:
        w_partner = 10.0
        w_partner_recent = 5.0
        w_opponent = 1.0
        w_opponent_recent = 0.5
        pk1 = self._pair_key(*t1)
        pk2 = self._pair_key(*t2)
        partner_pen = self.partner_count.get(pk1, 0) + self.partner_count.get(pk2, 0)
        partner_recent = (1 if self.partner_last_round.get(pk1, -99) == self.round_idx - 1 else 0) + \
                         (1 if self.partner_last_round.get(pk2, -99) == self.round_idx - 1 else 0)
        cross = [
            self._pair_key(t1[0], t2[0]), self._pair_key(t1[0], t2[1]),
            self._pair_key(t1[1], t2[0]), self._pair_key(t1[1], t2[1])
        ]
        opponent_pen = sum(self.opponent_count.get(k, 0) for k in cross)
        opponent_recent = sum(1 for k in cross if self.opponent_last_round.get(k, -99) == self.round_idx - 1)
        fairness = sum(self.matches_played[p] for p in t1 + t2) / 100.0
        return (
            w_partner * partner_pen +
            w_partner_recent * partner_recent +
            w_opponent * opponent_pen +
            w_opponent_recent * opponent_recent +
            fairness
        )

    # ---------- scoring ----------
    def record_results(self, games: List[Game], scores: List[str]) -> None:
        if len(games) != len(scores):
            raise ValueError("scores length must match number of games")
        for game, s in zip(games, scores):
            a, b = self._parse_score(s)
            game.scoreA, game.scoreB = a, b
            self._apply_game(game)

    def _parse_score(self, s: str) -> Tuple[int, int]:
        m = re.match(r"^\s*(\d+)\s*[-:]\s*(\d+)\s*$", s)
        if not m:
            raise ValueError(f"Invalid score '{s}'. Use e.g. 6-3")
        return int(m.group(1)), int(m.group(2))

    def _apply_game(self, g: Game) -> None:
        a1, a2 = g.teamA
        b1, b2 = g.teamB
        a, b = int(g.scoreA or 0), int(g.scoreB or 0)
        for p in (a1, a2):
            self.matches_played[p] += 1
            self.games_for[p] += a
            self.games_against[p] += b
            self.points[p] += a
        for p in (b1, b2):
            self.matches_played[p] += 1
            self.games_for[p] += b
            self.games_against[p] += a
            self.points[p] += b
        pkA = self._pair_key(a1, a2)
        pkB = self._pair_key(b1, b2)
        self.partner_count[pkA] = self.partner_count.get(pkA, 0) + 1
        self.partner_count[pkB] = self.partner_count.get(pkB, 0) + 1
        self.partner_last_round[pkA] = self.round_idx
        self.partner_last_round[pkB] = self.round_idx
        for x in (a1, a2):
            for y in (b1, b2):
                kk = self._pair_key(x, y)
                self.opponent_count[kk] = self.opponent_count.get(kk, 0) + 1
                self.opponent_last_round[kk] = self.round_idx

    # ---------- leaderboard ----------
    def leaderboard(self) -> List[Tuple[Player, int, int, int, int]]:
        def key(p: Player):
            return (-self.points[p], -(self.games_for[p] - self.games_against[p]), self.matches_played[p], p.lower())
        return [
            (p, self.points[p], self.matches_played[p], self.games_for[p], self.games_against[p])
            for p in sorted(self.players, key=key)
        ]

    # ---------- persistence helpers ----------
    def to_dict(self) -> dict:
        def game_to_dict(g: Game) -> dict:
            return {
                "court": g.court,
                "teamA": list(g.teamA),
                "teamB": list(g.teamB),
                "scoreA": g.scoreA,
                "scoreB": g.scoreB,
            }
        return {
            "players": self.players,
            "courts": self.courts,
            "round_idx": self.round_idx,
            "matches_played": self.matches_played,
            "games_for": self.games_for,
            "games_against": self.games_against,
            "points": self.points,
            "last_round": self.last_round,
            "partner_count": self.partner_count,
            "partner_last_round": self.partner_last_round,
            "opponent_count": self.opponent_count,
            "opponent_last_round": self.opponent_last_round,
            "rounds": [[game_to_dict(g) for g in rr] for rr in self.rounds],
        }

    @staticmethod
    def from_dict(d: dict) -> "Americano":
        am = Americano(d["players"], courts=int(d["courts"]))
        am.round_idx = int(d["round_idx"])
        am.matches_played = {k: int(v) for k, v in d["matches_played"].items()}
        am.games_for = {k: int(v) for k, v in d["games_for"].items()}
        am.games_against = {k: int(v) for k, v in d["games_against"].items()}
        am.points = {k: int(v) for k, v in d["points"].items()}
        am.last_round = {k: int(v) for k, v in d["last_round"].items()}
        am.partner_count = {k: int(v) for k, v in d["partner_count"].items()}
        am.partner_last_round = {k: int(v) for k, v in d["partner_last_round"].items()}
        am.opponent_count = {k: int(v) for k, v in d["opponent_count"].items()}
        am.opponent_last_round = {k: int(v) for k, v in d["opponent_last_round"].items()}
        am.rounds = []
        for rr in d["rounds"]:
            glist: List[Game] = []
            for g in rr:
                glist.append(Game(court=int(g["court"]), teamA=(g["teamA"][0], g["teamA"][1]), teamB=(g["teamB"][0], g["teamB"][1]), scoreA=g.get("scoreA"), scoreB=g.get("scoreB")))
            am.rounds.append(glist)
        return am