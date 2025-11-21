import chess
import chess.pgn
import pyspiel
import requests

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