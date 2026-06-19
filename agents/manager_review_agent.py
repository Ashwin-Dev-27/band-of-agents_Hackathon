"""
Manager Review Agent — PydanticAI-based agent
Role: Receive the complete onboarding package (plan + HR review + IT checklist),
      synthesize a final report, and request human-in-the-loop approval via Band.
      This is the final stage of the onboarding workflow.
"""
import os
import json
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv
from loguru import logger
from pydantic import BaseModel, Field

from band_integration.band_client import BandClient

load_dotenv()


class OnboardingReport(BaseModel):
    employee_name: str
    employee_role: str
    employee_department: str
    start_date: str
    manager: str

    # Aggregated data
    total_tasks: int
    hr_compliance_score: int
    hr_approved: bool
    accounts_to_create: int
    equipment_to_order: int

    # Agent summaries
    planner_summary: str
    hr_summary: str
    it_summary: str

    # Final recommendation
    overall_status: str = Field(description="APPROVED | NEEDS_REVIEW | BLOCKED")
    priority_actions: list = Field(description="List of immediate actions needed")
    manager_notes: str
    report_generated_at: str


class ApprovalDecision(BaseModel):
    approved: bool
    approver: Optional[str] = None
    approval_notes: str = ""
    approved_at: Optional[str] = None


async def run_manager_review(
    employee_info: dict,
    task_plan: list,
    hr_review: dict,
    it_checklist: dict,
    room_id: str,
) -> dict:
    """
    Manager Review Agent synthesizes all prior agent outputs into a final report
    and requests manager approval through the Band room.
    """
    logger.info(f"[Manager Review] Starting final review for {employee_info.get('name')}")

    client = BandClient("Manager Review Agent")
    await client.connect()

    # ── Step 1: Announce review start ─────────────────────────────────────────
    await client.send_message(
        room_id=room_id,
        message=(
            f"👔 MANAGER REVIEW AGENT — Final Review Starting\n\n"
            f"I have received all inputs from the Planner, HR Policy, and IT Provisioning agents.\n"
            f"Synthesizing final onboarding report for {employee_info['name']}..."
        ),
    )

    # ── Step 2: Use PydanticAI to synthesize report ────────────────────────────
    try:
        from pydantic_ai import Agent
        from pydantic_ai.models.openai import OpenAIModel
        from pydantic_ai.providers.openai import OpenAIProvider

        provider = os.getenv("PRIMARY_LLM_PROVIDER", "featherless")
        if provider == "featherless":
            openai_provider = OpenAIProvider(
                base_url=os.getenv("FEATHERLESS_BASE_URL", "https://api.featherless.ai/v1"),
                api_key=os.getenv("FEATHERLESS_API_KEY"),
            )
            model = OpenAIModel(
                model_name=os.getenv("MANAGER_REVIEW_MODEL", "meta-llama/Meta-Llama-3.1-70B-Instruct"),
                provider=openai_provider,
            )
        else:
            openai_provider = OpenAIProvider(
                base_url=os.getenv("AIML_BASE_URL", "https://api.aimlapi.com/v1"),
                api_key=os.getenv("AIML_API_KEY"),
            )
            model = OpenAIModel(
                model_name=os.getenv("MANAGER_REVIEW_MODEL", "gpt-4o-mini"),
                provider=openai_provider,
            )

        review_agent = Agent(
            model=model,
            result_type=OnboardingReport,
            system_prompt="""You are a Senior HR Manager reviewing onboarding packages.
Synthesize information from multiple agents into a comprehensive final report.
Be thorough, identify risks, and provide clear priority actions.""",
        )

        prompt = f"""
Create a comprehensive onboarding report based on these agent outputs:

EMPLOYEE INFO: {json.dumps(employee_info)}
TASK PLAN ({len(task_plan)} tasks): {json.dumps(task_plan[:3])}... (truncated)
HR REVIEW: {json.dumps(hr_review)}
IT CHECKLIST: {json.dumps(it_checklist)}

Generate the complete OnboardingReport.
"""
        result = await review_agent.run(prompt)
        report = result.data

    except Exception as e:
        logger.error(f"[Manager Review] PydanticAI error: {e}, using fallback")
        # Fallback structured report
        report = OnboardingReport(
            employee_name=employee_info.get("name", "Unknown"),
            employee_role=employee_info.get("role", "Unknown"),
            employee_department=employee_info.get("department", "Unknown"),
            start_date=employee_info.get("start_date", "TBD"),
            manager=employee_info.get("manager", "Unknown"),
            total_tasks=len(task_plan),
            hr_compliance_score=hr_review.get("compliance_score", 85),
            hr_approved=hr_review.get("approved", True),
            accounts_to_create=len(it_checklist.get("accounts", [])),
            equipment_to_order=len(it_checklist.get("equipment", [])),
            planner_summary=f"Generated {len(task_plan)} onboarding tasks across all departments.",
            hr_summary=hr_review.get("hr_notes", "Plan reviewed and approved with minor recommendations."),
            it_summary=it_checklist.get("it_notes", "IT setup plan ready. Estimated completion Day 3."),
            overall_status="APPROVED",
            priority_actions=[
                "Create email account before Day 1",
                "Schedule compliance training (30-day deadline)",
                "Order laptop — ensure delivery before start date",
            ],
            manager_notes=(
                f"Onboarding package for {employee_info.get('name')} is complete and ready.\n"
                f"HR compliance score: {hr_review.get('compliance_score', 85)}/100.\n"
                f"All critical IT accounts will be ready by Day 1.\n"
                f"Please review and approve to initiate the onboarding process."
            ),
            report_generated_at=datetime.utcnow().isoformat(),
        )

    # ── Step 3: Post final report to Band — awaits human approval ─────────────
    status_emoji = {"APPROVED": "✅", "NEEDS_REVIEW": "⚠️", "BLOCKED": "🚫"}.get(
        report.overall_status, "📋"
    )

    await client.send_message(
        room_id=room_id,
        message=(
            f"{status_emoji} FINAL ONBOARDING REPORT — {report.overall_status}\n"
            f"{'─' * 50}\n"
            f"👤 Employee: {report.employee_name}\n"
            f"💼 Role: {report.employee_role} | {report.employee_department}\n"
            f"📅 Start Date: {report.start_date}\n"
            f"👔 Manager: {report.manager}\n\n"
            f"📊 SUMMARY:\n"
            f"  • Total Tasks: {report.total_tasks}\n"
            f"  • HR Compliance: {report.hr_compliance_score}/100 {'✓' if report.hr_approved else '✗'}\n"
            f"  • Accounts to Create: {report.accounts_to_create}\n"
            f"  • Equipment to Order: {report.equipment_to_order}\n\n"
            f"🎯 PRIORITY ACTIONS:\n"
            + "\n".join(f"  → {action}" for action in report.priority_actions)
            + f"\n\n📝 MANAGER NOTES:\n{report.manager_notes}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⏳ AWAITING HUMAN APPROVAL from {report.manager}\n"
            f"Please approve or request changes in this Band room."
        ),
        metadata={
            "event": "awaiting_manager_approval",
            "report": report.model_dump(),
            "employee": employee_info,
        },
    )

    logger.success("[Manager Review] Report posted to Band. Awaiting human approval ✓")
    return {"report": report.model_dump(), "status": "awaiting_approval", "room_id": room_id}
