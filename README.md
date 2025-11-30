# Agentifying Chess Benchmark

This is the code for agentifying a chess benchmark. This codebase uses the template from the following codebases:
https://github.com/agentbeats/agentify-example-tau-bench
https://github.com/google-deepmind/game_arena/tree/main

This project is inspired by the following chess benchmark: https://www.kaggle.com/game-arena

## Project Structure

```
src/
├── green_agent/    # Assessment manager agent
├── white_agent/    # Target agent being tested
└── launcher.py     # Evaluation coordinator
```

## Project Description

The green agent expects two white agent urls. It will initiate a game between the two white agents.

Prompt: the green agent will send each agent the move history, the current board position in FEN format, and a list of all legal moves + indexes. It expects the white agent to return the index of its chosen move, along with reasoning.

For each move, the green agent will provide a per-move evaluation (clp for centipawn loss) to determine how good the move is.

After the game is done, the green agent will adjust each white agent's elo depending on the result. In addition, average clp statistics will be returned. Finally, the green agent will also print out the full game.

The green agent will also store the following files in a Google Cloud Storage Bucket:

elo_raings.json: a dictionary with ratings of all players

game.pgn: the game file

game_data.json: full output file containing model prompt, model response, and game evaluation

game_eval.json: a running list of the game evaluation

player_data.json: the clp for each player


## Installation and Usage

Create a Google Cloud Storage bucket, do the necessary authentication.

Configure the environment variables:

export OPENAI_API_KEY="[your OpenAI API key]"

export AGENT_BUCKET="[your GCS bucket]"

export TEST_MODE="false"

Now, configure the chess engine. There will be separate steps for Local Mode and Remote Mode, but the directory structure should look like this:

```
engines/
└── stockfish-mac # or stockfish-linux
src/
├── green_agent/
├── white_agent/
└── launcher.py
```


Please refer to the following sections for Local Mode and Remote Mode.

## Local Mode

### Setting up the Chess Engine

Run `brew install stockfish`

Find the binary file that is generated and put it in the current directory: engines/stockfish-mac

In src/my_util/utils.py, set the ENGINE_PATH variable to "engines/stockfish-mac" (line 59)

```
ENGINE_PATH = "engines/stockfish-mac"
```

### Running the Code

Install uv. `brew install uv` for mac.

Run the following to configure the uv environment:

```bash
uv sync
```

Now, to run the evaluation using the green agent and two basic white agents:

```bash
uv run python main.py launch -l
```

### Test Cases

To reproduce the three test cases, set the following environment variables:

export TEST_MODE="True"

export TEST_INDEX="0"

The test case to be ran is controlled by TEST_INDEX, and right now, it can be set to "0", "1", or "2".


## Remote Mode

There is already a running VM with the agent code, so deploying to VM is not necessary. However, if you want to deploy your own agent instance, feel do the following steps:

Create your own VM instance on GCP, and give it permissions to access your GCS bucket.

Install conda, git clone this repository, and create a conda environment with python=3.13.

Activate the conda environment, and install all the packages in requirements.txt

### Setting up the Chess Engine

Run `apt install -y stockfish` (assuming in root)

Find the stockfish binary file and put it in engines/stockfish-linux

In src/my_util/utils.py, set the ENGINE_PATH variable to "engines/stockfish-linux" (line 59)

```
ENGINE_PATH = "engines/stockfish-linux"
```

### Starting the Agent in VM

Run the following command:

```bash
CLOUDRUN_HOST="[your domain name]" \
PORT=8010 \
HTTPS_ENABLED=true \
agentbeats run_ctrl
```

For your domain name, do not include the https:// at the beginning, and do not include a / at the end. As an example, here is what I ran:

```bash
CLOUDRUN_HOST="jlu-green-agent-v4.ngrok.dev" \
PORT=8010 \
HTTPS_ENABLED=true \
agentbeats run_ctrl
```

And the controller will be located at https://jlu-green-agent-v4.ngrok.dev

Now, you can add this agent to Agentbeats.

### Using ngrok

This project's agent was done using ngrok. Please consult ngrok documentation for how to set this up. To start the ngrok domain, do the following in a separate terminal (through tmux):

ngrok http --url=jlu-green-agent-v4.ngrok.dev 8010

Replace the url and port with whatever you are using.

### Basic White Agents

Although white agents are not part of this project, if you want to use the basic white agents, you can use the following setup:

Duplicate the code repository two times (one for each white agent).

In `main.py`, change the "role" from "green" to "white" and change the agent_port to be something unique.

```
class ChessbenchSettings(BaseSettings):
    role: str = "green" # change this
    host: str = "127.0.0.1"
    agent_port: int = 9010
```

Now, for each white agent, run:

```bash
CLOUDRUN_HOST="[new domain name]" \
PORT=[new port] \
HTTPS_ENABLED=true \
agentbeats run_ctrl
```
The white agents will now be ready. Note that you will need to use tmux to start multiple terminal sessions.