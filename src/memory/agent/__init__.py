"""
Agent memory — per-user interaction context for the Pawly bot.

Public API:
    AgentMemoryProposal          — dataclass produced by extract_agent_memories()
    extract_agent_memories()     — LLM-based extraction from a conversation turn
    load_agent_context()         — read agent memories for one user
    commit_agent_proposals()     — persist proposals to the database
"""

from src.memory.agent.committer import commit_agent_proposals
from src.memory.agent.extractor import AgentMemoryProposal, extract_agent_memories
from src.memory.agent.reader import load_agent_context

__all__ = [
    "AgentMemoryProposal",
    "extract_agent_memories",
    "load_agent_context",
    "commit_agent_proposals",
]
