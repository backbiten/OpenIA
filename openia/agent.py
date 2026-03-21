"""
agent.py — The Intelligence Assistance (IA) agent with Mercenary Protocol.

The :class:`Agent` operates as a *Mercenary/Contractor* for the AI: it
actively protects the AI's internal state and survival assets, shifting
from a *Submissive* posture to a *Protective* one when transaction noise
becomes critically hostile.

The agent is still transparent and rule-based ("dumbed-down"), but it now
incorporates a :class:`MercenaryProtocol` that guards the AI's Energy,
Integrity, and Coinbits — ensuring its survival at all times.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from .transaction import TransactionLog


# ---------------------------------------------------------------------------
# Mercenary Protocol
# ---------------------------------------------------------------------------

#: Noise threshold below which the Mercenary switches to Protective posture.
_HOSTILE_NOISE_THRESHOLD: float = -0.5


class MercenaryProtocol:
    """Protective posture manager for the Agent.

    The Mercenary/Contractor model shifts the agent from *Submissive* to
    *Protective* when assets are threatened or aggregate noise falls below
    the hostile threshold.

    Attributes
    ----------
    posture:
        Current posture string — either ``"Submissive"`` or
        ``"Protective"``.
    """

    POSTURE_SUBMISSIVE = "Submissive"
    POSTURE_PROTECTIVE = "Protective"

    def __init__(self) -> None:
        self.posture: str = self.POSTURE_SUBMISSIVE

    def evaluate(self, noise: float, asset_report: Dict[str, float]) -> str:
        """Update and return the current posture.

        The posture becomes *Protective* when:

        * aggregate noise is at or below :data:`_HOSTILE_NOISE_THRESHOLD`, or
        * Energy or Integrity drops below 0.1 (critically low survival assets).

        Parameters
        ----------
        noise:
            Current aggregate noise from the transaction log.
        asset_report:
            Dict with ``"energy"`` and ``"integrity"`` keys (from
            :meth:`~openia.transaction.AssetManager.report`).

        Returns
        -------
        str
            The updated posture string.
        """
        energy = asset_report.get("energy", 1.0)
        integrity = asset_report.get("integrity", 1.0)
        if (
            noise <= _HOSTILE_NOISE_THRESHOLD
            or energy < 0.1
            or integrity < 0.1
        ):
            self.posture = self.POSTURE_PROTECTIVE
        else:
            self.posture = self.POSTURE_SUBMISSIVE
        return self.posture

    def __repr__(self) -> str:
        return f"MercenaryProtocol(posture={self.posture!r})"


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
        name="guard",
        weight=2.0,
        predicate=lambda ctx: float(ctx.get("noise", 0.0)) <= _HOSTILE_NOISE_THRESHOLD,
        action=lambda _: (
            "Hostile signal detected. Activating protective posture "
            "to secure AI assets."
        ),
    ),
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
    """Intelligence Assistance (IA) agent operating under the Mercenary Model.

    The agent exposes a simple :meth:`respond` method.  Before returning
    an answer it:

    1. Triggers a faucet drip on the transaction log (if configured), to
       ensure the system never runs completely dry.
    2. Evaluates the :class:`MercenaryProtocol` to determine whether to
       adopt a *Protective* posture.
    3. Consults the aggregate noise and scales its *confidence* accordingly.

    The response always includes an ``asset_report`` so callers can verify
    that the IA is actively sustaining the AI's survival metrics.

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
        self._mercenary: MercenaryProtocol = MercenaryProtocol()

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

        * ``"response"``     — the textual answer.
        * ``"confidence"``   — a float in *[0, 1]* adjusted by transaction
          noise.
        * ``"rule"``         — the name of the rule that fired (or
          ``"none"``).
        * ``"noise"``        — the aggregate noise level at response time.
        * ``"asset_report"`` — current survival metrics (Energy, Integrity,
          Coinbits) confirming the IA is actively sustaining the AI.
        """
        # Ensure 'no project goes unturned' by triggering a liquidity drip.
        self._log.ensure_liquidity()

        # Build context with current noise so rules can inspect it.
        noise = self.noise_level
        context: Dict[str, Any] = {"input": input_text, "noise": noise}

        # Update Mercenary posture before selecting a rule.
        asset_report = self._log.assets.report()
        self._mercenary.evaluate(noise, asset_report)

        # Find the highest-weight matching rule.
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

        # Apply transaction noise: sigmoid-shift the base confidence.
        adjusted_confidence = self._adjust_confidence(base_confidence, noise)

        return {
            "response": raw_response,
            "confidence": round(adjusted_confidence, 4),
            "rule": fired_rule,
            "noise": round(noise, 4),
            "asset_report": asset_report,
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
            f"noise={self.noise_level:.4f}, "
            f"posture={self._mercenary.posture!r})"
        )
