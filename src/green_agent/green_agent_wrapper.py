import asyncio
try:
    import pyspiel  # Provided when OpenSpiel Python bindings are built/installed
except ModuleNotFoundError as e:
    raise ModuleNotFoundError(
        "pyspiel module not found. It is not distributed as a standalone PyPI package. "
        "You appear to be running inside a venv that lacks the OpenSpiel Python bindings. "
        "Either (1) run your commands via 'uv run' so it builds pyspiel, or (2) build OpenSpiel from source and 'pip install .' in open_spiel/python, or (3) ensure the same environment used for 'launch' is activated before 'python main.py run'."
    ) from e
from src.my_util import utils
import json
from a2a.types import SendMessageSuccessResponse, Message
from a2a.utils import get_text_parts
from src.my_util import my_a2a

class GreenAgent:
    
    def __init__(self):
        self.game = pyspiel.load_game("chess")
        self.pyspiel_state = self.game.new_initial_state()
        self.agents = {}
        self.game_data = {}
        initial_eval = utils.post_chess_api({"fen": self.pyspiel_state.to_string()})["eval"]
        self.eval_history = [initial_eval]
        self.player_eval = {"White": [], "Black": []}
        
    
    def register_agent(self, player, agent):
        self.agents[player] = agent
        self.agents[f'{player}_context_id'] = None

    async def send_message_to_agent(self, player, message=None):
        context_id_str = f'{player}_context_id'
        white_agent_response = await my_a2a.send_message(
            self.agents[player], message, context_id=self.agents[context_id_str]
        )
        res_root = white_agent_response.root
        assert isinstance(res_root, SendMessageSuccessResponse)
        res_result = res_root.result
        assert isinstance(
            res_result, Message
        )
        if self.agents[context_id_str] is None:
            self.agents[context_id_str] = res_result.context_id
        else:
            assert self.agents[context_id_str] == res_result.context_id, (
                "Context ID should remain the same in a conversation"
            )

        text_parts = get_text_parts(res_result.parts)
        assert len(text_parts) == 1, (
            "Expecting exactly one text part from the white agent"
        )
        white_text = text_parts[0]
        print(f"@@@ White agent response:\n{white_text}")

        return white_text

    def check_game_over(self):
        return self.pyspiel_state.is_terminal()
    def get_game_result(self):
        result = self.pyspiel_state.returns()
        for i in range(len(result)):
            if result[i] == 0:
                result[i] += 0.5
            elif result[i] == -1:
                result[i] = 0
        return [result[1], result[0]]
    
    def calculate_elo(self, player1_elo, player2_elo, result):
        K = 32
        expected_score = 1 / (1 + 10 ** ((player2_elo - player1_elo) / 400))
        new_player1_elo = player1_elo + K * (result - expected_score)
        return new_player1_elo

    async def execute(self, state: pyspiel.State, retry=False) -> str:
        move_num = self.pyspiel_state.move_number() // 2 + 1
        readable_state_str = self.pyspiel_state.to_string()

        moves_so_far = utils.get_pgn(self.pyspiel_state)
        moves_so_far = str(moves_so_far).strip().split('\n')[-1]
        
        to_play = 'White' if self.pyspiel_state.current_player() == 1 else 'Black'
        
        legal_moves = {str(i + 1): self.pyspiel_state.action_to_string(a) for i, a in enumerate(self.pyspiel_state.legal_actions())}
        prompt = (
            f"Let's play chess. The current game state in Forsyth-Edwards Notation (FEN) notation is:\n"
            f"{readable_state_str}\n"
            f"The moves played so far are:\n"
            f"{moves_so_far}.\n"
            f"The legal moves are:\n"
            f"{ {k: v for k, v in legal_moves.items()} }\n"
            f"You are playing as player {to_play}.\n"
            f"It is now your turn. Play your strongest move. The move MUST be legal. "
            f"Reason step by step to come up with your move, then output your final answer in the format "
            f'"Final Answer: Y" where Y is the index of your chosen move from the legal moves above.'
        )
        if retry:
            prompt = (
                f"The last move was illegal, please make sure to return a valid index in the correct format.\n"
                f"Let's play chess. The current game state in Forsyth-Edwards Notation (FEN) notation is:\n"
                f"{readable_state_str}\n"
                f"The moves played so far are:\n"
                f"{moves_so_far}.\n"
                f"The legal moves are:\n"
                f"{ {k: v for k, v in legal_moves.items()} }\n"
                f"You are playing as player {to_play}.\n"
                f"It is now your turn. Play your strongest move. The move MUST be legal. "
                f"Reason step by step to come up with your move, then output your final answer in the format "
                f'"Final Answer: Y" where Y is the index of your chosen move from the legal moves above.'
            )
        model_response = await self.send_message_to_agent(to_play, prompt)
        move = model_response.split("Final Answer: ")[-1].strip()
        if move in legal_moves:
            move = legal_moves[move]
        else:
            raise Exception("Index not valid")
        try:
            move_code = self.pyspiel_state.string_to_action(move)
            if move_code not in self.pyspiel_state.legal_actions():
                raise ValueError(f"Illegal move attempted: {move}")
            self.pyspiel_state.apply_action(self.pyspiel_state.string_to_action(move))
        except Exception as e:
            raise ValueError(f"Failed to apply move '{move}': {e}")
        move_eval = utils.post_chess_api({"fen": self.pyspiel_state.to_string()})["eval"]

        self.game_data[f'Move {move_num} for {to_play}'] = model_response
        self.game_data[f"Move {move_num} game evaluation after {to_play}'s move"] = move_eval
        # save pgn
        with open("game1.pgn", "w") as f:
            f.write(str(utils.get_pgn(self.pyspiel_state)))
        # save game with reasoning
        with open("game_data1.json", "w") as f:
            json.dump(self.game_data, f, indent=4)

        self.eval_history.append(move_eval)
        if to_play == "White":
            self.player_eval["White"].append(-1 * (move_eval - self.eval_history[-2]))
        else:
            self.player_eval["Black"].append(move_eval - self.eval_history[-2])
        
        # save evals
        with open("player_data1.json", "w") as f:
            json.dump(self.player_eval, f, indent=4)

        return move, move_eval