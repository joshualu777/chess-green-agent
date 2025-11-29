import chess
import chess.pgn
import pyspiel
import requests
import json
import os
import atexit
from google.cloud import storage

GAME_FILE="game.pgn"
GAME_DATA_FILE="game_data.json"
GAME_EVAL_FILE="game_eval.json"
PLAYER_DATA_FILE="player_data.json"

# Source: https://github.com/google-deepmind/game_arena/tree/main
def get_pgn(target_state, player_names=None) -> chess.pgn.Game:
    if player_names is None:
        player_names = ["Black", "White"]
    game = pyspiel.load_game("chess")
    state = game.new_initial_state()
    moves = []
    for action in target_state.history():
        # Append move in UCI notation.
        moves.append(pyspiel.chess.action_to_move(action, state.board()).to_lan())
        state.apply_action(action)

    # Create a new game.
    pgn_game = chess.pgn.Game()
    pgn_game.headers["Event"] = "Chess Game"
    pgn_game.headers["White"] = player_names[1]
    pgn_game.headers["Black"] = player_names[0]
    # Add results header.
    if target_state.is_terminal():
        score = {
            -1: "0",
            0: "1/2",
            1: "1",
        }
        int_returns = [score[x] for x in target_state.returns()]
        # Note: Results are 'white-black', while returns are 'black, white'.
        result = "-".join(reversed(int_returns))
    else:
        result = "*"
    pgn_game.headers["Result"] = result
    # Add moves to the game.
    pgn_game.add_line([chess.Move.from_uci(move) for move in moves])
    return pgn_game

def post_chess_api(data=None):
    if data is None:
        data = {}
    response = requests.post(
        "https://chess-api.com/v1",
        headers={"Content-Type": "application/json"},
        json=data
    )
    return response.json()

ENGINE_PATH = "engines/stockfish-mac"
_engine = None

def get_engine():
    global _engine
    if _engine is None:
        try:
            _engine = chess.engine.SimpleEngine.popen_uci(ENGINE_PATH)
        except Exception as e:
            raise RuntimeError(f"Failed to start chess engine: {e}")
    return _engine

def close_engine():
    global _engine
    if _engine is not None:
        try:
            _engine.quit()
        except Exception as e:
            print(f"Failed to quit chess engine: {e}")
        _engine = None

atexit.register(close_engine)

def get_engine_eval(fen, depth=15):
    engine = get_engine()
    board = chess.Board(fen)
    info = engine.analyse(board, chess.engine.Limit(depth=depth))
    score = info["score"].pov(chess.WHITE)
    cp = score.score(mate_score=1500)
    eval_pawns = cp / 100.0
    return eval_pawns

BUCKET_NAME = os.environ["AGENT_BUCKET"]

def save_state_to_gcs(state, object_name):
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(object_name)

    payload = json.dumps(state)
    blob.upload_from_string(payload, content_type="application/json")

def save_pgn_to_gcs(pgn_text, object_name):
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(object_name)

    blob.upload_from_string(pgn_text, content_type="application/x-chess-pgn")

def load_state_from_gcs(object_name):
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(object_name)

    if not blob.exists():
        return None

    contents = blob.download_as_text()
    return json.loads(contents)
