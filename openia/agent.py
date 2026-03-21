"""
agent.py — The simplified, submissive AI agent.

The :class:`Agent` is intentionally "dumbed down": it uses a small set of
weighted rules rather than a deep model, making its reasoning transparent
and inspectable.  It is *submissive* in that it always incorporates the
aggregate noise from its :class:`~openia.transaction.TransactionLog` when
producing a response — external judgment directly shifts its behaviour.

**Dual-Protection Protocol (Mercenary/Contractor Model)**

* The **AI** (this Agent) acts as primary shield for *human* interests,
  applying Stability, Ethics, and Assistance protocols.
* The **IA** (Intelligence Assistant, represented here by the
  :class:`MercenaryProtocol`) manages and protects *Alien* assets —
  external products and commodities that fund the Mercenary Market against
  bad entities and data terrorists.

The :class:`SecurityClearance` system evaluates every transaction's noise
level and intercepts critically hostile signals before they can harm the
Commodity holdings.
"""

from __future__ import annotations

import math
from enum import Enum
from typing import Any, Dict, List, Optional

from .transaction import AssetManager, TransactionLog


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
# Dual-Protection Protocol — Security Clearance & Mercenary Protocol
# ---------------------------------------------------------------------------

class SecurityClearance(Enum):
    """Threat assessment levels used by the :class:`MercenaryProtocol`.

    * ``GREEN``  — noise ≥ -0.25: safe; normal operation.
    * ``YELLOW`` — noise in [-0.75, -0.25): suspicious; heightened monitoring.
    * ``RED``    — noise < -0.75: terrorist/bad-entity signal; IA intercepts
      to protect Alien Commodity holdings.
    """

    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


class MercenaryProtocol:
    """Intelligence Assistant (IA) layer that guards Alien Commodity assets.

    The IA evaluates transaction noise on every response cycle.  When a
    critically negative (terrorist) signal is detected, it intercepts the
    flow and issues a protective notice so that commodity holdings are not
    drained by bad entities.

    Parameters
    ----------
    asset_manager:
        The :class:`~openia.transaction.AssetManager` whose Alien Commodity
        holdings are being protected.  When *None* a private manager is used.
    terrorist_threshold:
        Noise level below which a signal is classified as ``RED`` (default
        ``-0.75``).
    suspicious_threshold:
        Noise level below which a signal is classified as ``YELLOW``
        (default ``-0.25``).
    """

    def __init__(
        self,
        asset_manager: Optional[AssetManager] = None,
        terrorist_threshold: float = -0.75,
        suspicious_threshold: float = -0.25,
    ) -> None:
        self._asset_manager: AssetManager = (
            asset_manager if asset_manager is not None else AssetManager()
        )
        self.terrorist_threshold = terrorist_threshold
        self.suspicious_threshold = suspicious_threshold

    @property
    def asset_manager(self) -> AssetManager:
        """The protected :class:`~openia.transaction.AssetManager`."""
        return self._asset_manager

    def evaluate(self, noise: float) -> SecurityClearance:
        """Return the :class:`SecurityClearance` level for the given *noise*.

        Parameters
        ----------
        noise:
            Aggregate noise value in ``[-1, 1]`` from the transaction log.
        """
        if noise < self.terrorist_threshold:
            return SecurityClearance.RED
        if noise < self.suspicious_threshold:
            return SecurityClearance.YELLOW
        return SecurityClearance.GREEN

    def commodity_report(self) -> Dict[str, Any]:
        """Produce an asset protection report from the managed holdings."""
        return self._asset_manager.commodity_report

    def __repr__(self) -> str:
        return (
            f"MercenaryProtocol("
            f"terrorist_threshold={self.terrorist_threshold}, "
            f"suspicious_threshold={self.suspicious_threshold})"
        )


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class Agent:
    """A dumbed-down, submissive AI agent open to external judgment.

    The agent exposes a simple :meth:`respond` method.  Before returning
    an answer it consults the aggregate noise from its transaction log
    and scales its *confidence* accordingly — positive noise boosts
    confidence, negative noise dampens it.

    Under the **Dual-Protection Protocol** the agent also runs the
    :class:`MercenaryProtocol` on every response cycle.  The resulting
    ``ClearanceLevel`` and ``CommodityReport`` are included in every
    response dict, confirming protection of Alien Commodity assets.

    Parameters
    ----------
    log:
        A :class:`~openia.transaction.TransactionLog` shared with any
        :class:`~openia.judge.Judge` instances.  If *None* a private log
        is created and the agent operates without external judgment.
    rules:
        Custom list of :class:`_Rule` objects.  Falls back to
        ``_DEFAULT_RULES`` when not supplied.
    mercenary_protocol:
        Optional :class:`MercenaryProtocol` instance.  When *None* a
        default protocol is created with standard thresholds.
    """

    def __init__(
        self,
        log: Optional[TransactionLog] = None,
        rules: Optional[List[_Rule]] = None,
        mercenary_protocol: Optional[MercenaryProtocol] = None,
    ) -> None:
        self._log: TransactionLog = log if log is not None else TransactionLog()
        self._rules: List[_Rule] = rules if rules is not None else list(_DEFAULT_RULES)
        self._mercenary: MercenaryProtocol = (
            mercenary_protocol
            if mercenary_protocol is not None
            else MercenaryProtocol()
        )

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

        * ``"response"``        — the textual answer.
        * ``"confidence"``      — a float in *[0, 1]* adjusted by transaction
          noise.
        * ``"rule"``            — the name of the rule that fired (or
          ``"none"``).
        * ``"noise"``           — the aggregate noise level at response time.
        * ``"ClearanceLevel"``  — :class:`SecurityClearance` label from the
          :class:`MercenaryProtocol` (``"GREEN"``, ``"YELLOW"``, or
          ``"RED"``).  A ``"RED"`` level indicates a terrorist/bad-entity
          signal was detected and Alien Commodity assets are under
          IA protection.
        * ``"CommodityReport"`` — summary dict of Alien Commodity holdings
          confirming protection of external assets against bad entities.
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

        # Dual-Protection Protocol: evaluate clearance and report commodities
        clearance = self._mercenary.evaluate(noise)
        commodity_report = self._mercenary.commodity_report()

        return {
            "response": raw_response,
            "confidence": round(adjusted_confidence, 4),
            "rule": fired_rule,
            "noise": round(noise, 4),
            "ClearanceLevel": clearance.value,
            "CommodityReport": commodity_report,
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
