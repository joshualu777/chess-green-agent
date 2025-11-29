"""Green agent implementation - manages assessment and evaluation."""

import uvicorn
import tomllib
import dotenv
import json
import time
import os
import datetime as dt
import numpy as np
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCard, SendMessageSuccessResponse, Message
from a2a.utils import new_agent_text_message, get_text_parts
from src.my_util import parse_tags, my_a2a
from src.my_util.utils import save_state_to_gcs, save_pgn_to_gcs, load_state_from_gcs, GAME_FILE, GAME_DATA_FILE, PLAYER_DATA_FILE, GAME_EVAL_FILE
from src.green_agent.green_agent_wrapper import GreenAgent

dotenv.load_dotenv()

ELO_OBJECT_NAME="elo_ratings.json"
DEFAULT_ELO=1000

def load_agent_card_toml(agent_name):
    current_dir = __file__.rsplit("/", 1)[0]
    with open(f"{current_dir}/{agent_name}.toml", "rb") as f:
        return tomllib.load(f)


async def ask_agent_to_solve(white_agent_url_1, white_agent_url_2):
    # Here, instead of calling white agent like calling an LLM, we need to present
    #   the assessment scenario to the white agent as if it is a independent task
    # Specifically, here we provide the tool information for the agent to reply with
    green_agent = GreenAgent()
    green_agent.register_agent("White", white_agent_url_1)
    green_agent.register_agent("Black", white_agent_url_2)
    is_retry = False
    while green_agent.check_game_over() is False:
        try:
            cur_result = await green_agent.execute(green_agent.pyspiel_state, is_retry)
            is_retry = False
            print(cur_result)
        except:
            is_retry = True
            print("Illegal move made, try again")
    game_result = green_agent.get_game_result()
    
    agent_elo = load_state_from_gcs(ELO_OBJECT_NAME)
    if agent_elo is None:
        agent_elo = {}

    white_agent_1_elo = agent_elo.get(white_agent_url_1, DEFAULT_ELO)
    white_agent_2_elo = agent_elo.get(white_agent_url_2, DEFAULT_ELO)

    white_agent_new_elo1 = green_agent.calculate_elo(white_agent_1_elo, white_agent_2_elo, game_result[0])
    white_agent_new_elo2 = green_agent.calculate_elo(white_agent_2_elo, white_agent_1_elo, game_result[1])
    
    print(f'Game result: {game_result}')
    print(f'Adjusted elos: {white_agent_new_elo1}, {white_agent_new_elo2}')
    agent_elo[white_agent_url_1] = white_agent_new_elo1
    agent_elo[white_agent_url_2] = white_agent_new_elo2
    save_state_to_gcs(agent_elo, ELO_OBJECT_NAME)

    store_files(white_agent_url_1, white_agent_url_2)

    return game_result, agent_elo, green_agent.player_eval


class ChessGreenAgentExecutor(AgentExecutor):
    def __init__(self):
        pass

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        # parse the task
        print("Green agent: Received a task, parsing...")
        user_input = context.get_user_input()
        tags = parse_tags(user_input)
        white_agent_url_1 = tags["white_agent_url"][0]
        white_agent_url_2 = tags["white_agent_url"][1]
        # env_config_str = tags["env_config"][0]
        # env_config = json.loads(env_config_str)

        # set up the environment
        print("Green agent: Setting up the environment...")
        metrics = {white_agent_url_1: {}, white_agent_url_2: {}}

        print("Green agent: Starting evaluation...")
        timestamp_started = time.time()
        game_res, elo, res = await ask_agent_to_solve(white_agent_url_1, white_agent_url_2)

        metrics["elapsed_time"] = time.time() - timestamp_started
        metrics["game_result"] = game_res

        metrics[white_agent_url_1]["elo"] = elo[white_agent_url_1]
        metrics[white_agent_url_1]["clp"] = float(np.mean(res["White"]["Overall"])) if res["White"]["Overall"] else None
        metrics[white_agent_url_1]["clp_equal"] = float(np.mean(res["White"]["Equal"])) if res["White"]["Equal"] else None
        metrics[white_agent_url_1]["clp_winning"] = float(np.mean(res["White"]["Winning"])) if res["White"]["Winning"] else None
        metrics[white_agent_url_1]["clp_losing"] = float(np.mean(res["White"]["Losing"])) if res["White"]["Losing"] else None

        metrics[white_agent_url_2]["elo"] = elo[white_agent_url_2]
        metrics[white_agent_url_2]["clp"] = float(np.mean(res["Black"]["Overall"])) if res["Black"]["Overall"] else None
        metrics[white_agent_url_2]["clp_equal"] = float(np.mean(res["Black"]["Equal"])) if res["Black"]["Equal"] else None
        metrics[white_agent_url_2]["clp_winning"] = float(np.mean(res["Black"]["Winning"])) if res["Black"]["Winning"] else None
        metrics[white_agent_url_2]["clp_losing"] = float(np.mean(res["Black"]["Losing"])) if res["Black"]["Losing"] else None

        print("Green agent: Evaluation complete")
        print("Printing out game file:")
        try:
            with open(GAME_FILE, "r") as f:
                print(f.read())
        except FileNotFoundError:
            print(f"{GAME_FILE} not found.")
        except Exception as e:
            print(f"Failed to read {GAME_FILE}: {e}")

        print("\nPrinting out metrics:")
        print(metrics)

        await event_queue.enqueue_event(
            new_agent_text_message(
                f"Finished. Metrics: {metrics}\n"
            )
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError


def start_green_agent(agent_name="chess_green_agent", host="localhost", port=9001, local=False):
    print("Starting green agent for chess benchmark...")
    agent_card_dict = load_agent_card_toml(agent_name)
    
    # # without controller
    if local:
        url = f"http://{host}:{port}"
        agent_card_dict["url"] = url  # complete all required card fields
    else:
        agent_card_dict["url"] = os.getenv("AGENT_URL")
        print("Printing agent card:")
        print(agent_card_dict)

    request_handler = DefaultRequestHandler(
        agent_executor=ChessGreenAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )

    app = A2AStarletteApplication(
        agent_card=AgentCard(**agent_card_dict),
        http_handler=request_handler,
    )

    uvicorn.run(app.build(), host=host, port=port)

def clean_url(str):
    return (
        str.replace("://", "_")
            .replace("/", "_")
            .replace("?", "_")
            .replace("&", "_")
    )

def store_files(white_url_1, white_url_2):
    now = dt.datetime.now(dt.timezone.utc)
    timestamp = now.strftime("%Y%m%dT%H%M%S%fZ")
    game_string = clean_url(f'{white_url_1}_vs_{white_url_2}_{timestamp}')

    try:
        with open(GAME_FILE, "r", encoding="utf-8") as f:
            pgn_text = f.read()
    except:
        pgn_text = ""
    save_pgn_to_gcs(pgn_text, f"{game_string}_{GAME_FILE}")

    try:
        with open(GAME_DATA_FILE, "r") as f:
            game_data = json.load(f)
    except:
        game_data = {}
    save_state_to_gcs(game_data, f"{game_string}_{GAME_DATA_FILE}")

    try:
        with open(PLAYER_DATA_FILE, "r") as f:
            player_data = json.load(f)
    except:
        player_data = {}
    save_state_to_gcs(player_data, f"{game_string}_{PLAYER_DATA_FILE}")

    try:
        with open(GAME_EVAL_FILE, "r") as f:
            game_eval = json.load(f)
    except:
        game_eval = {}
    save_state_to_gcs(game_eval, f"{game_string}_{GAME_EVAL_FILE}")
