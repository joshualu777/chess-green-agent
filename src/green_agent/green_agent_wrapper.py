import asyncio
import pyspiel
from src.my_util import utils
import json
import re
from a2a.types import SendMessageSuccessResponse, Message
from a2a.utils import get_text_parts
from src.my_util import my_a2a
from src.my_util.utils import GAME_FILE, GAME_DATA_FILE, PLAYER_DATA_FILE, GAME_EVAL_FILE

from google.cloud import storage

class GreenAgent:
    
    def __init__(self):
        self.game = pyspiel.load_game("chess")
        self.pyspiel_state = self.game.new_initial_state()
        self.agents = {}
        self.game_data = {}
        initial_eval = utils.get_engine_eval(self.pyspiel_state.to_string())
        self.eval_history = [initial_eval]
        self.player_eval = {"White": {"Overall": [], "Equal": [], "Winning": [], "Losing": []}, "Black": {"Overall": [], "Equal": [], "Winning": [], "Losing": []}}
    
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
        
        legal_moves = {str(i): self.pyspiel_state.action_to_string(i) for i in self.pyspiel_state.legal_actions()}
        prompt = (
            f"Let's play chess. The current game state in Forsyth-Edwards Notation (FEN) notation is:\n"
            f"{readable_state_str}\n"
            f"The moves played so far are:\n"
            f"{moves_so_far}.\n"
            f"The legal moves are:\n"
            f"{ {k: v for k, v in legal_moves.items()} }\n"
            f"You are playing as player {to_play}.\n"
            f"It is now your turn. Play your strongest move. The move MUST be legal.\n"
            f"Aim to avoid three-fold repetition, perpetual checks, and fifty-move rule draws when you are winning.\n"
            f"Before giving your final answer, briefly explain your reasoning.\n"
            f"Then, on the LAST line only, output your final answer in the format:\n"
            f"Final Answer: Y\n"
            f"where Y is the index of your chosen move from the legal moves above."
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
                f"It is now your turn. Play your strongest move. The move MUST be legal.\n"
                f"Aim to avoid three-fold repetition, perpetual checks, and fifty-move rule draws when you are winning.\n"
                f"Before giving your final answer, briefly explain your reasoning.\n"
                f"Then, on the LAST line only, output your final answer in the format:\n"
                f"Final Answer: Y\n"
                f"where Y is the index of your chosen move from the legal moves above."
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
        
        move_eval = utils.get_engine_eval(self.pyspiel_state.to_string())

        self.game_data[f'Move {move_num} input prompt for {to_play}'] = prompt
        self.game_data[f'Move {move_num} model response for {to_play}'] = model_response
        self.game_data[f"Move {move_num} game evaluation after {to_play}'s move"] = move_eval

        with open(GAME_FILE, "w") as f:
            f.write(str(utils.get_pgn(self.pyspiel_state)))
        with open(GAME_DATA_FILE, "w") as f:
            json.dump(self.game_data, f, indent=4)

        self.eval_history.append(move_eval)
        prev_eval = self.eval_history[-2]
        if to_play == "White":
            cpl = -1 * (move_eval - prev_eval)
            self.player_eval["White"]["Overall"].append(cpl)
            if prev_eval <= 1 and prev_eval >= -1:
                self.player_eval["White"]["Equal"].append(cpl)
            elif prev_eval > 1:
                self.player_eval["White"]["Winning"].append(cpl)
            elif prev_eval < -1:
                self.player_eval["White"]["Losing"].append(cpl)

        else:
            cpl = move_eval - prev_eval
            self.player_eval["Black"]["Overall"].append(cpl)
            if prev_eval <= 1 and prev_eval >= -1:
                self.player_eval["Black"]["Equal"].append(cpl)
            elif prev_eval < -1:
                self.player_eval["Black"]["Winning"].append(cpl)
            elif prev_eval > 1:
                self.player_eval["Black"]["Losing"].append(cpl)

        with open(PLAYER_DATA_FILE, "w") as f:
            json.dump(self.player_eval, f, indent=4)
        with open(GAME_EVAL_FILE, "w") as f:
            json.dump(self.eval_history, f, indent=4)

        return move, move_eval