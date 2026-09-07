"""Policy engine: the ONLY component that sets execution_allowed. LLM text never decides it."""

from __future__ import annotations

from director.config import Mode, PoliciesConfig, Settings
from director.contracts.reasoning import ActionType
from director.contracts.rules import RuleResult

SPEND_CHANGING = {
    ActionType.PROPOSE_BUDGET_INCREASE,
    ActionType.PROPOSE_BUDGET_DECREASE,
    ActionType.PAUSE_TEST,
}
POLICY_VERSION = "1"


def execution_allowed(
    settings: Settings, policies: PoliciesConfig, rule: RuleResult, action: ActionType
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if settings.kill_switch:
        reasons.append("KILL_SWITCH")
    if settings.mode == Mode.OBSERVE or not settings.execution_enabled:
        reasons.append("MODE_OBSERVE")
    if action not in SPEND_CHANGING:
        reasons.append("ACTION_NOT_EXECUTABLE")
    if rule.blocking_gates:
        reasons.extend(f"GATE:{g}" for g in rule.blocking_gates)
    if action in SPEND_CHANGING and not policies.execution.allowed_accounts:
        reasons.append("NO_ALLOWED_ACCOUNTS")
    return (not reasons), reasons
