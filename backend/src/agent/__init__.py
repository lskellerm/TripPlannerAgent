"""Agent module — Pydantic AI agent configuration, schemas, and chat endpoints."""

from src.agent.agent import (
	AGENT_INSTRUCTIONS,
	agent,
	airbnb_toolset,
	chrome_devtools_server,
	configure_agent_model,
	ensure_ollama_model,
	model,
)
from src.agent.schemas import TripWeek

__all__: list[str] = [
	"AGENT_INSTRUCTIONS",
	"TripWeek",
	"agent",
	"airbnb_toolset",
	"chrome_devtools_server",
	"configure_agent_model",
	"ensure_ollama_model",
	"model",
]
