from __future__ import annotations

from fastapi import APIRouter

from opspilot_schema.envelope import make_success
from opspilot_schema.policy_rule import RiskPolicyRule

from .rules import load_rules_from_db, save_rules

router = APIRouter(prefix="/api/v1/policy", tags=["policy"])


@router.get("/rules")
async def get_policy_rules():
    return make_success([rule.model_dump() for rule in load_rules_from_db()])


@router.put("/rules")
async def put_policy_rules(body: list[RiskPolicyRule]):
    save_rules(body)
    return make_success({"updated": len(body)})
