# Agentify Example: Tau-Bench

Example code for agentifying Tau-Bench using A2A and MCP standards.

## Project Structure

```
src/
├── green_agent/    # Assessment manager agent
├── white_agent/    # Target agent being tested
└── launcher.py     # Evaluation coordinator
```

## Installation

```bash
uv sync
```

## Usage

First, configure `.env` with `OPENAI_API_KEY=...`, then

```bash
# Launch complete evaluation
uv run python main.py launch
```

## pyspiel / OpenSpiel Installation

The `python main.py run` command imports `pyspiel` directly. The `pyspiel` module is not on PyPI and is only available after building OpenSpiel's Python bindings. Using `uv run` may succeed if a cached build exists, while your plain virtual environment may not have the compiled extension.

Install OpenSpiel bindings inside your current venv:

```bash
# (from project root)
source .venv/bin/activate  # ensure you're in the project venv
git clone https://github.com/deepmind/open_spiel.git
cd open_spiel
pip install --upgrade pip setuptools wheel
pip install numpy
brew install cmake swig  # if not already installed
mkdir build && cd build
cmake -DPython3_EXECUTABLE=$(which python) ..
make -j$(sysctl -n hw.logicalcpu)
cd ../open_spiel/python
pip install .
cd ../../..  # back to project root
python -c "import pyspiel; print('pyspiel installed:', pyspiel.__file__)"
```

After successful installation, you can run:

```bash
python main.py run --help
python main.py run
```

If `ModuleNotFoundError: pyspiel` persists:
- Confirm you activated the same venv used for installation.
- Run `python -c "import sys; print(sys.executable)"` to verify interpreter.
- Ensure no conflicting `PYTHONPATH` or `uv run` transient environment.

The code will raise a clear message if `pyspiel` is not found (see `green_agent_wrapper.py`).
