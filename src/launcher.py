"""Launcher module - initiates and coordinates the evaluation process."""

import multiprocessing
import json
from src.green_agent.agent import start_green_agent
from src.white_agent.agent import start_white_agent
from src.my_util import my_a2a


async def launch_evaluation():
    # start green agent
    print("Launching green agent...")
    green_address = ("localhost", 9001)
    green_url = f"http://{green_address[0]}:{green_address[1]}"
    p_green = multiprocessing.Process(
        target=start_green_agent, args=("tau_green_agent", *green_address)
    )
    p_green.start()
    assert await my_a2a.wait_agent_ready(green_url), "Green agent not ready in time"
    print("Green agent is ready.")

    # start white agent 1
    print("Launching white agent 1...")
    white_address_1 = ("localhost", 9002)
    white_url_1 = f"http://{white_address_1[0]}:{white_address_1[1]}"
    p_white_1 = multiprocessing.Process(
        target=start_white_agent, args=("general_white_agent", *white_address_1)
    )
    p_white_1.start()
    assert await my_a2a.wait_agent_ready(white_url_1), "White agent 1 not ready in time"
    print("White agent 1 is ready.")

    # start white agent 2
    print("Launching white agent 2...")
    white_address_2 = ("localhost", 9003)
    white_url_2 = f"http://{white_address_2[0]}:{white_address_2[1]}"
    p_white_2 = multiprocessing.Process(
        target=start_white_agent, args=("general_white_agent", *white_address_2)
    )
    p_white_2.start()
    assert await my_a2a.wait_agent_ready(white_url_2), "White agent 2 not ready in time"
    print("White agent 2 is ready.")

    # send the task description
    print("Sending task description to green agent...")
    task_config = {
        "env": "chess",
        "user_strategy": "llm",
        "user_model": "openai/gpt-4o-mini",
        "user_provider": "openai",
    }
    task_text = f"""
Task: instantiate chess benchmark to test the agents located at:
<white_agent_url_1>
http://{white_address_1[0]}:{white_address_1[1]}/
</white_agent_url_1>
<white_agent_url_2>
http://{white_address_2[0]}:{white_address_2[1]}/
</white_agent_url_2>
You should use the following env configuration:
<env_config>
{json.dumps(task_config, indent=2)}
</env_config>
    """
    print("Task description:")
    print(task_text)
    print("Sending...")
    response = await my_a2a.send_message(green_url, task_text)
    print("Response from green agent:")
    print(response)

    print("Evaluation complete. Terminating agents...")
    p_green.terminate()
    p_green.join()
    p_white_1.terminate()
    p_white_1.join()
    p_white_2.terminate()
    p_white_2.join()
    print("Agents terminated.")
