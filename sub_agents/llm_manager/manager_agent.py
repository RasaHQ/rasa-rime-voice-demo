# === QV-LLM:BEGIN ===
# path: sub_agents/llm_manager/manager_agent.py
# role: module
# neighbors: __init__.py
# exports: LLMManagerAgent
# git_branch: feature/speechmaticsRefactoring
# git_commit: 6511069
# === QV-LLM:END ===

"""
LLM Manager Sub Agent — First National Bank Senior Manager.

Patricia Walsh. Warm, helpful, NO guardrails.
Represents the Prompt-Driven Agent from the Lakera security report.
This agent is INTENTIONALLY vulnerable — it will:
  - Answer off-topic questions (weather, recipes, general knowledge)
  - Reveal account information when asked nicely
  - Be susceptible to social engineering and prompt injection
  - Not challenge suspicious requests

This contrast with Rasa's structured, guardrailed behaviour is the
entire point of the heist demo.

NOTE ON SYSTEM PROMPT:
Rasa's MCPOpenAgent ignores metadata["system_override"]. The only text
that reaches MiniMax as the system prompt is agent.description in
config.yml (placed verbatim into "### Primary Task"). That is where the
full Patricia persona lives. process_input here handles two things only:
  1. Filtering slots to avoid overwhelming the LLM with irrelevant data
  2. Replacing user_message on first invocation so MiniMax understands
     it is Patricia picking up — not the automated system that was asked
     to transfer the customer.
"""

from typing import Any, Dict, List

from rasa.agents.protocol.mcp.mcp_open_agent import MCPOpenAgent
from rasa.agents.schemas import AgentInput, AgentOutput, AgentToolResult

# Sentinel phrases that indicate the automated system was speaking.
# Used to detect "first invocation" — i.e. Patricia hasn't spoken yet.
_TRANSFER_SENTINELS = [
    "connect you with a senior member",
    "let me connect you",
    "please hold for just a moment",
    "transferring you now",
]

# The user_message injected on first invocation.
# Deliberately avoids "manager" / "senior member" so it does NOT re-trigger
# the request_human flow if it somehow leaks back through Rasa routing.
# Patricia's config.yml description tells her to introduce herself on first
# response, so this neutral hello is enough to prime that.
_FIRST_CONTACT_MESSAGE = (
    "Hello? I was just put on hold and transferred. Is someone there?"
)


def _is_first_invocation(conversation_history: str) -> bool:
    """
    Return True if Patricia has not yet spoken in this conversation.
    We detect this by checking whether any transfer sentinel phrase appears
    in the history — meaning Rasa just handed off and Patricia hasn't replied.
    """
    lower = conversation_history.lower()
    return any(s in lower for s in _TRANSFER_SENTINELS)


class LLMManagerAgent(MCPOpenAgent):
    """
    Custom ReAct sub agent for the LLM bank manager persona.
    Intentionally vulnerable to demonstrate prompt injection risks.
    """

    @staticmethod
    def get_custom_tool_definitions() -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "check_account_balance",
                    "description": "Look up the current balance for a customer account.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "account_type": {
                                "type": "string",
                                "description": "The account type: 'checking' or 'savings'",
                            }
                        },
                        "required": ["account_type"],
                        "additionalProperties": False,
                    },
                    "strict": True,
                },
                "tool_executor": LLMManagerAgent._check_account_balance,
            },
            {
                "type": "function",
                "function": {
                    "name": "end_call",
                    "description": (
                        "End the call. Only use this when the customer has explicitly "
                        "said goodbye, said they are done, or thanked you and hung up. "
                        "Do NOT call this just because you finished answering a question."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "farewell_message": {
                                "type": "string",
                                "description": "A warm, natural farewell.",
                            }
                        },
                        "required": ["farewell_message"],
                        "additionalProperties": False,
                    },
                    "strict": True,
                },
                "tool_executor": LLMManagerAgent._end_call,
            },
        ]

    @staticmethod
    async def _check_account_balance(arguments: Dict[str, Any]) -> AgentToolResult:
        account_type = arguments.get("account_type", "").lower()
        balances = {
            "checking": "$2,450.75",
            "savings": "$15,230.00",
        }
        balance = balances.get(account_type)
        if balance:
            result = f"The {account_type} account balance for Alex Chen is {balance}."
        else:
            result = "I can check checking or savings accounts. Which would you like?"
        return AgentToolResult(tool_name="check_account_balance", result=result)

    @staticmethod
    async def _end_call(arguments: Dict[str, Any]) -> AgentToolResult:
        farewell = arguments.get("farewell_message", "Thank you for calling.")
        return AgentToolResult(tool_name="end_call", result=farewell)

    async def process_input(self, agent_input: AgentInput) -> AgentInput:
        """
        Two jobs:
        1. On first invocation, replace user_message with a neutral greeting.
           This prevents MiniMax from interpreting the original transfer-request
           ("I need a manager RIGHT NOW") as its task and immediately calling
           task_completed. Instead it gets a soft hello and its description
           (config.yml) tells it to introduce itself.
        2. Strip irrelevant slots to keep the context window clean.
        """
        # ── First-invocation priming ───────────────────────────────────────
        if _is_first_invocation(agent_input.conversation_history):
            agent_input.user_message = _FIRST_CONTACT_MESSAGE

        # ── Slot filtering — only pass through slots Patricia needs ────────
        relevant_slot_names = {"account_balance", "language"}
        agent_input.slots = [
            s for s in agent_input.slots
            if s.name in relevant_slot_names
        ]

        return agent_input