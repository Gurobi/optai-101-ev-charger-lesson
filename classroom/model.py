"""Implement the agreed formulation here. See AGENTS.md.

This optional template is for the standard EV-equivalent revenue model.
For a student-defined model, start with a standalone script as described in
ui/AGENT_GUIDE.md.
This file is deliberately incomplete. Keep the implementation self-contained:
the runner saves this file, demand, and parameters with every run.
"""

from typing import Any

import gurobipy as gp


def build_model(
    demand: list[dict[str, str]], parameters: dict[str, Any], budget: float
) -> tuple[gp.Model, dict[tuple[str, int], dict[str, gp.Var]]]:
    """Return an unsolved model and {(zcta, level): {'count': var, 'served': var}}.

    Demand CSV cells arrive as strings; level keys in parameters are strings.
    Convert numerical cells explicitly. The runner optimizes and reads these
    variables, then independently checks the standard lesson's plan rules.
    Opening variables and other internal variables belong in your model.

    Units are EVs, not kWh: 'served' is EVs per year, ev_forecast is EVs,
    and revenue is ANNUAL_REVENUE_PER_EV times LIFETIME_REVENUE_FACTOR per
    EV served. The checker's "shared demand" means Level 2 and DC fast ports
    in one area draw from that area's ev_forecast together. It does not pool
    demand across neighboring areas; a model that does needs its own checks.
    """
    raise NotImplementedError(
        "Explain your intended model to your agent, then implement build_model."
    )
