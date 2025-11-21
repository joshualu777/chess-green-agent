"""Green agent implementation - manages assessment and evaluation."""

import uvicorn
import tomllib
import dotenv
import json
import time
import os
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCard, SendMessageSuccessResponse, Message
from a2a.utils import new_agent_text_message, get_text_parts
from src.my_util import parse_tags, my_a2a
from src.green_agent.green_agent_wrapper import GreenAgent

dotenv.load_dotenv()


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
        except Exception as e:
            is_retry = True
            print("Illegal move made, try again: ", e)
    game_result = green_agent.get_game_result()
    # new_elo1 = green_agent.calculate_elo(white_agent_1.elo, white_agent_2.elo, game_result[0])
    # new_elo2 = green_agent.calculate_elo(white_agent_2.elo, white_agent_1.elo, game_result[1])
    print(game_result)
    # print(f'Adjusted elos: {new_elo1}, {new_elo2}')
    # white_agent_1.elo = new_elo1
    # white_agent_2.elo = new_elo2
    print(f'Player move metrics: White: {sum(green_agent.player_eval["White"])}, Black: {sum(green_agent.player_eval["Black"])}')

    return (sum(green_agent.player_eval["White"]), sum(green_agent.player_eval["Black"]))


class TauGreenAgentExecutor(AgentExecutor):
    def __init__(self):
        pass

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        # parse the task
        print("Green agent: Received a task, parsing...")
        user_input = context.get_user_input()
        tags = parse_tags(user_input)
        white_agent_url_1 = tags["white_agent_url_1"]
        white_agent_url_2 = tags["white_agent_url_2"]
        env_config_str = tags["env_config"]
        env_config = json.loads(env_config_str)

        # set up the environment
        # migrate from https://github.com/sierra-research/tau-bench/blob/4754e6b406507dbcbce8e8b3855dcf80aaec18ac/tau_bench/run.py#L20
        print("Green agent: Setting up the environment...")
        metrics = {}

        print("Green agent: Starting evaluation...")
        timestamp_started = time.time()
        res = await ask_agent_to_solve(white_agent_url_1, white_agent_url_2)

        metrics["time_used"] = time.time() - timestamp_started

        print("Green agent: Evaluation complete.")
        await event_queue.enqueue_event(
            new_agent_text_message(
                f"Finished. Metrics: {res}\n"
            )
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError


def start_green_agent(agent_name="tau_green_agent", host="localhost", port=9001):
    print("Starting green agent...")
    agent_card_dict = load_agent_card_toml(agent_name)
    
    # # without controller
    # url = f"http://{host}:{port}"
    # agent_card_dict["url"] = url  # complete all required card fields

    agent_card_dict["url"] = os.getenv("AGENT_URL")

    request_handler = DefaultRequestHandler(
        agent_executor=TauGreenAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )

    app = A2AStarletteApplication(
        agent_card=AgentCard(**agent_card_dict),
        http_handler=request_handler,
    )

    uvicorn.run(app.build(), host=host, port=port)
