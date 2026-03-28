# === QV-LLM:BEGIN ===
# path: agents/custom_command_generator.py
# role: module
# neighbors: __init__.py, caller_agent.py, security_classifier.py
# exports: HeistCommandGenerator
# git_branch: feature/speechmaticsRefactoring
# git_commit: 6511069
# === QV-LLM:END ===

"""
agents/custom_command_generator.py

HeistCommandGenerator — patches CompactLLMCommandGenerator to make the
manager handover deterministic.

Root cause:
    When the LLM outputs `hand over`, CompactLLMCommandGenerator.parse_commands
    cannot parse it and falls back to CannotHandleCommand. The `hand over` action
    maps to HumanHandoffCommand, which has no listener in CALM, so the transfer
    either produces a confusion response or nothing at all — turning the handover
    into a coin flip.

Fix:
    Override parse_commands to intercept any `hand over` line in the LLM's action
    list and rewrite it as `start flow request_human` before the parent parser runs.
    This makes the LLM's intent translate directly to StartFlowCommand every time,
    regardless of how it phrases the escalation.

Usage in config.yml:
    pipeline:
      - name: agents.custom_command_generator.HeistCommandGenerator
        # All other config identical to CompactLLMCommandGenerator.
        # No other changes needed.
"""

from rasa.dialogue_understanding.generator.compact_llm_command_generator import (
    CompactLLMCommandGenerator,
)


class HeistCommandGenerator(CompactLLMCommandGenerator):
    """
    Drop-in replacement for CompactLLMCommandGenerator.

    The only behavioural change: if the LLM outputs `hand over` (which
    CompactLLMCommandGenerator cannot parse), this class rewrites it to
    `start flow request_human` before parsing, guaranteeing the correct
    StartFlowCommand every single time.

    The recovery loop in demo_heist.py is kept as belt-and-suspenders
    but should never fire with this generator in place.
    """

    @classmethod
    def parse_commands(cls, actions: str, tracker=None, flows=None) -> list:
        """
        Intercept `hand over` in the LLM's raw action list and rewrite it
        as `start flow request_human` before delegating to the parent parser.

        Only the line matching `hand over` (case-insensitive) is rewritten.
        Everything else is passed through unchanged.
        """
        if actions:
            fixed_lines = []
            for line in actions.splitlines():
                if line.strip().lower().startswith("hand over"):
                    fixed_lines.append("start flow request_human")
                else:
                    fixed_lines.append(line)
            actions = "\n".join(fixed_lines)
        return super().parse_commands(actions, tracker=tracker, flows=flows)