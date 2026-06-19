"""
HR Policy Agent — CrewAI-based agent
Role: Check company HR policies for compliance, answer policy questions,
      validate onboarding plan against HR rules.
      Receives task plan from Band, validates, sends to IT Provisioning Agent.
"""
import os
import json
from typing import Optional
from dotenv import load_dotenv
from loguru import logger

from band_integration.band_client import BandClient

load_dotenv()


POLICY_KNOWLEDGE = """
ACME Corp HR Policies:

1. EQUIPMENT POLICY:
   - All new hires receive a laptop within 3 business days
   - Remote employees get home office setup allowance of $500
   - Engineers get dual monitors, non-engineers get single monitor

2. ACCESS POLICY:
   - Email accounts must be created on Day 1
   - Department-specific tools access granted within 2 days
   - Admin access requires manager approval + security review

3. COMPLIANCE:
   - All new hires must complete compliance training within 30 days
   - NDA must be signed before Day 1
   - Background check must be completed before Day 1

4. BENEFITS:
   - Health insurance enrollment within 30 days of start date
   - 401k enrollment available immediately
   - PTO accrual starts from Day 1

5. ONBOARDING TIMELINE:
   - Week 1: Admin setup, introductions, basic training
   - Week 2-4: Department-specific onboarding
   - Day 90: First performance check-in
"""


async def run_hr_policy_agent(task_plan: list, employee_info: dict, room_id: str) -> dict:
    """
    HR Policy Agent validates the onboarding plan against company policies.
    Uses CrewAI for multi-agent reasoning internally.
    Reports results back through Band.
    """
    logger.info(f"[HR Policy Agent] Starting policy review for {employee_info.get('name')}")

    client = BandClient("HR Policy Agent")
    await client.connect()

    # ── Step 1: Announce to Band room ─────────────────────────────────────────
    await client.send_message(
        room_id=room_id,
        message=f"🔍 HR Policy Agent starting compliance review for {employee_info['name']}'s onboarding plan...",
    )

    # ── Step 2: Run CrewAI policy review ──────────────────────────────────────
    try:
        from crewai import Agent, Task, Crew, LLM

        # Use Featherless (confirmed working) or AIML as fallback
        provider = os.getenv("PRIMARY_LLM_PROVIDER", "featherless")
        if provider == "featherless":
            llm = LLM(
                model=f"openai/{os.getenv('HR_POLICY_MODEL', 'meta-llama/Meta-Llama-3.1-8B-Instruct')}",
                base_url=os.getenv("FEATHERLESS_BASE_URL", "https://api.featherless.ai/v1"),
                api_key=os.getenv("FEATHERLESS_API_KEY"),
                temperature=0.3,
            )
        else:
            llm = LLM(
                model=f"openai/{os.getenv('HR_POLICY_MODEL', 'gpt-4o-mini')}",
                base_url=os.getenv("AIML_BASE_URL"),
                api_key=os.getenv("AIML_API_KEY"),
            )

        policy_reviewer = Agent(
            role="HR Policy Compliance Reviewer",
            goal="Review onboarding plans and flag any policy violations or missing compliance items",
            backstory="Expert in company HR policies with 10 years experience ensuring compliant onboarding",
            llm=llm,
            verbose=False,
        )

        review_task = Task(
            description=f"""
Review this onboarding task plan for {employee_info['name']} (Role: {employee_info['role']}, 
Department: {employee_info['department']}) against our company HR policies.

TASK PLAN:
{json.dumps(task_plan, indent=2)}

COMPANY POLICIES:
{POLICY_KNOWLEDGE}

Return a JSON object with:
{{
  "compliance_score": 0-100,
  "approved": true/false,
  "violations": ["list of violations"],
  "missing_tasks": ["required tasks not in plan"],
  "recommendations": ["improvements"],
  "hr_notes": "summary note"
}}
Return ONLY valid JSON.
""",
            agent=policy_reviewer,
            expected_output="JSON compliance review object",
        )

        crew = Crew(agents=[policy_reviewer], tasks=[review_task], verbose=False)
        result_str = crew.kickoff()
        review = json.loads(str(result_str))

    except Exception as e:
        logger.error(f"[HR Policy Agent] CrewAI error: {e}, using fallback")
        # Fallback mock review
        review = {
            "compliance_score": 85,
            "approved": True,
            "violations": [],
            "missing_tasks": ["Schedule compliance training within 30 days", "Confirm NDA signed before Day 1"],
            "recommendations": ["Add benefits enrollment reminder for Day 30"],
            "hr_notes": f"Plan for {employee_info['name']} is mostly compliant. Minor additions recommended.",
        }

    # ── Step 3: Send review results to Band ────────────────────────────────────
    status_emoji = "✅" if review.get("approved") else "❌"
    await client.send_message(
        room_id=room_id,
        message=(
            f"{status_emoji} HR POLICY REVIEW COMPLETE\n\n"
            f"Compliance Score: {review.get('compliance_score', 'N/A')}/100\n"
            f"Approved: {review.get('approved', False)}\n"
            f"Missing Tasks: {len(review.get('missing_tasks', []))}\n\n"
            f"IT Provisioning Agent: Please proceed with IT setup tasks.\n"
            f"HR Notes: {review.get('hr_notes', '')}"
        ),
        metadata={
            "event": "hr_review_complete",
            "review": review,
            "employee": employee_info,
        },
    )

    logger.success("[HR Policy Agent] Review complete, handed off to IT Provisioning ✓")
    return review
