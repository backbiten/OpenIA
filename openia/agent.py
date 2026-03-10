"""
agent.py — The simplified, submissive AI agent.

The :class:`Agent` is intentionally "dumbed down": it uses a small set of
weighted rules rather than a deep model, making its reasoning transparent
and inspectable.  It is *submissive* in that it always incorporates the
aggregate noise from its :class:`~openia.transaction.TransactionLog` when
producing a response — external judgment directly shifts its behaviour.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from .transaction import TransactionLog


# ---------------------------------------------------------------------------
# Internal rule engine
# ---------------------------------------------------------------------------

class _Rule:
    """A single weighted decision rule."""

    def __init__(self, name: str, weight: float, predicate, action) -> None:
        self.name = name
        self.weight = weight          # higher weight → more influential
        self._predicate = predicate   # (context: dict) -> bool
        self._action = action         # (context: dict) -> Any

    def matches(self, context: Dict[str, Any]) -> bool:
        try:
            return bool(self._predicate(context))
        except Exception:
            return False

    def apply(self, context: Dict[str, Any]) -> Any:
        return self._action(context)


_DEFAULT_RULES: List[_Rule] = [
    _Rule(
        name="echo",
        weight=1.0,
        predicate=lambda ctx: "input" in ctx,
        action=lambda ctx: f"Received: {ctx['input']}",
    ),
    _Rule(
        name="help",
        weight=1.5,
        predicate=lambda ctx: str(ctx.get("input", "")).lower().startswith("help"),
        action=lambda _: "How can I assist you?",
    ),
    _Rule(
        name="status",
        weight=1.5,
        predicate=lambda ctx: str(ctx.get("input", "")).lower() in {"status", "ping"},
        action=lambda _: "I am operational.",
    ),
]


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class Agent:
    """A dumbed-down, submissive AI agent open to external judgment.

    The agent exposes a simple :meth:`respond` method.  Before returning
    an answer it consults the aggregate noise from its transaction log
    and scales its *confidence* accordingly — positive noise boosts
    confidence, negative noise dampens it.

    Parameters
    ----------
    log:
        A :class:`~openia.transaction.TransactionLog` shared with any
        :class:`~openia.judge.Judge` instances.  If *None* a private log
        is created and the agent operates without external judgment.
    rules:
        Custom list of :class:`_Rule` objects.  Falls back to
        ``_DEFAULT_RULES`` when not supplied.
    """

    def __init__(
        self,
        log: Optional[TransactionLog] = None,
        rules: Optional[List[_Rule]] = None,
    ) -> None:
        self._log: TransactionLog = log if log is not None else TransactionLog()
        self._rules: List[_Rule] = rules if rules is not None else list(_DEFAULT_RULES)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def log(self) -> TransactionLog:
        """The transaction log the agent is listening to."""
        return self._log

    @property
    def noise_level(self) -> float:
        """Current aggregate noise from the transaction log."""
        return self._log.aggregate_noise

    def respond(self, input_text: str) -> Dict[str, Any]:
        """Generate a response to *input_text*.

        Returns a dict with:

        * ``"response"`` — the textual answer.
        * ``"confidence"`` — a float in *[0, 1]* adjusted by transaction
          noise.
        * ``"rule"`` — the name of the rule that fired (or ``"none"``).
        * ``"noise"`` — the aggregate noise level at response time.
        """
        context: Dict[str, Any] = {"input": input_text}

        # Find the highest-weight matching rule
        best: Optional[_Rule] = None
        for rule in self._rules:
            if rule.matches(context):
                if best is None or rule.weight > best.weight:
                    best = rule

        raw_response: str
        base_confidence: float
        fired_rule: str

        if best is not None:
            raw_response = str(best.apply(context))
            base_confidence = min(1.0, best.weight / 2.0)
            fired_rule = best.name
        else:
            raw_response = "I don't know how to respond to that."
            base_confidence = 0.1
            fired_rule = "none"

        # Apply transaction noise: sigmoid-shift the base confidence
        noise = self.noise_level
        adjusted_confidence = self._adjust_confidence(base_confidence, noise)

        return {
            "response": raw_response,
            "confidence": round(adjusted_confidence, 4),
            "rule": fired_rule,
            "noise": round(noise, 4),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _adjust_confidence(base: float, noise: float) -> float:
        """Shift *base* confidence by *noise* using a soft clamp.

        ``noise`` is in [-1, 1].  Positive noise moves confidence toward
        1; negative noise moves it toward 0.
        """
        shifted = base + noise * 0.5
        # Soft clamp via sigmoid to stay in (0, 1)
        return 1.0 / (1.0 + math.exp(-6.0 * (shifted - 0.5)))

    def __repr__(self) -> str:
        return (
            f"Agent(rules={len(self._rules)}, "
            f"noise={self.noise_level:.4f})"
        )
