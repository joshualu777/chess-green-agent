"""CLI entry point for agentify chess benchmark."""

import typer
import asyncio

from src.green_agent.agent import start_green_agent
from src.white_agent.agent import start_white_agent
from src.launcher import launch_evaluation, launch_remote_evaluation
from pydantic_settings import BaseSettings


class ChessbenchSettings(BaseSettings):
    role: str = "green"
    host: str = "127.0.0.1"
    agent_port: int = 9010

app = typer.Typer(help="Agentified Chess-Bench - Standardized agent assessment framework")


@app.command()
def green():
    """Start the green agent (assessment manager)."""
    start_green_agent()


@app.command()
def white():
    """Start the white agent (target being tested)."""
    start_white_agent()

@app.command()
def run():
    settings = ChessbenchSettings()
    if settings.role == "green":
        start_green_agent(host=settings.host, port=settings.agent_port)
    elif settings.role == "white":
        start_white_agent(host=settings.host, port=settings.agent_port)
    else:
        raise ValueError(f"Unknown role: {settings.role}")
    return

@app.command()
def launch(local: bool = typer.Option(False, "--local", "-l")):
    """Launch the complete evaluation workflow."""
    asyncio.run(launch_evaluation(local=local))

@app.command()
def launch_remote(green_url: str, white_url_1: str, white_url_2: str):
    """Launch the complete evaluation workflow."""
    asyncio.run(launch_remote_evaluation(green_url, white_url_1, white_url_2))


if __name__ == "__main__":
    app()
