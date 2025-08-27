from __future__ import annotations
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from starlette.templating import Jinja2Templates

from .americano import Americano, Tournament, Store
from .schemas import CreateTournamentIn, TournamentOut, RoundOut, ScoresIn, LeaderRow

BASE_DIR = Path(__file__).parent
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))
# Either cast to str (works everywhere) or rely on new Store accepting PathLike
store = Store(str(BASE_DIR.parent / "data"))

app = FastAPI(title="Padel Americano API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"ok": True, "service": "padel-americano", "ui": "/ui", "endpoints": [
        "/tournaments (GET, POST)",
        "/tournaments/{tid} (GET)",
        "/tournaments/{tid}/rounds/next (POST)",
        "/tournaments/{tid}/rounds/{round}/scores (POST)",
        "/tournaments/{tid}/rounds/current (GET)",
        "/tournaments/{tid}/leaderboard (GET)",
        "/tournaments/{tid}/board (GET HTML)",
    ]}

# ---- API ----
@app.get("/tournaments")
def list_tournaments():
    return store.list()

@app.post("/tournaments", response_model=TournamentOut)
def create_tournament(inp: CreateTournamentIn):
    tid = uuid.uuid4().hex[:10]
    am = Americano(players=inp.players, courts=inp.courts)
    t = Tournament(id=tid, name=inp.name, americano=am)
    store.save(t)
    return {"id": t.id, "name": t.name, "players": am.players, "courts": am.courts, "round_idx": am.round_idx}

@app.get("/tournaments/{tid}", response_model=TournamentOut)
def get_tournament(tid: str):
    try:
        t = store.load(tid)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Tournament not found")
    am = t.americano
    return {"id": t.id, "name": t.name, "players": am.players, "courts": am.courts, "round_idx": am.round_idx}

@app.post("/tournaments/{tid}/rounds/next", response_model=RoundOut)
def next_round(tid: str):
    try:
        t = store.load(tid)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Tournament not found")
    am = t.americano
    matches = am.next_round()
    store.save(t)
    return {"round_idx": am.round_idx, "matches": [{"court": g.court, "teamA": list(g.teamA), "teamB": list(g.teamB)} for g in matches]}

@app.get("/tournaments/{tid}/rounds/current", response_model=RoundOut)
def get_current_round(tid: str):
    try:
        t = store.load(tid)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Tournament not found")
    am = t.americano
    if am.round_idx == 0:
        return {"round_idx": 0, "matches": []}
    games = am.rounds[-1]
    return {"round_idx": am.round_idx, "matches": [{"court": g.court, "teamA": list(g.teamA), "teamB": list(g.teamB), "scoreA": g.scoreA, "scoreB": g.scoreB} for g in games]}

@app.post("/tournaments/{tid}/rounds/{round_no}/scores")
def post_scores(tid: str, round_no: int, body: ScoresIn):
    try:
        t = store.load(tid)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Tournament not found")
    am = t.americano
    if am.round_idx != round_no:
        raise HTTPException(status_code=409, detail=f"Scores must be submitted for current round {am.round_idx}.")
    if round_no < 1 or round_no > len(am.rounds):
        raise HTTPException(status_code=404, detail="Round not found")
    games = am.rounds[round_no - 1]
    # prevent double submission unless we add an explicit overwrite flag
    if any((g.scoreA is not None or g.scoreB is not None) for g in games):
        raise HTTPException(status_code=409, detail="Scores already submitted for this round.")
    try:
        am.record_results(games, body.scores)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    store.save(t)
    return {"ok": True, "leaderboard": _leaderboard_payload(am)}

@app.get("/tournaments/{tid}/leaderboard", response_model=List[LeaderRow])
def get_leaderboard(tid: str):
    try:
        t = store.load(tid)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Tournament not found")
    return _leaderboard_payload(t.americano)

# ---- HTML ----
@app.get("/tournaments/{tid}/board", response_class=HTMLResponse)
def board_html(request: Request, tid: str):
    try:
        t = store.load(tid)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Tournament not found")
    am = t.americano
    rows = _leaderboard_payload(am)
    return TEMPLATES.TemplateResponse("board.html", {"request": request, "t": t, "am": am, "rows": rows})

@app.get("/ui", response_class=HTMLResponse)
@app.get("/ui/{tid}", response_class=HTMLResponse)
def ui(request: Request, tid: Optional[str] = None):
    return TEMPLATES.TemplateResponse("ui.html", {"request": request, "tid": tid})

# ---- helpers ----
def _leaderboard_payload(am: Americano) -> List[dict]:
    return [{"player": p, "points": pts, "matches": mp, "gf": gf, "ga": ga} for (p, pts, mp, gf, ga) in am.leaderboard()]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)