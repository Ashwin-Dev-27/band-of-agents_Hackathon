"""
IT Provisioning Agent — LangGraph-based agent
Role: Generate IT setup checklist, create account provisioning requests,
      and coordinate equipment setup for new hires.
      Receives from HR Policy Agent via Band, sends to Manager Review Agent.
"""
import os
import json
from typing import TypedDict
from datetime import datetime, timedelta
from dotenv import load_dotenv
from loguru import logger

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from band_integration.band_client import BandClient

load_dotenv()


# ─── State Definition ─────────────────────────────────────────────────────────
class ITProvisioningState(TypedDict):
    employee_info: dict
    task_plan: list
    hr_review: dict
    it_checklist: dict
    room_id: str
    status: str


# ─── LangGraph Nodes ──────────────────────────────────────────────────────────
def generate_it_checklist(state: ITProvisioningState) -> ITProvisioningState:
    """Node 1: Generate IT provisioning checklist using LLM."""
    info = state["employee_info"]
    name = info.get('name', info.get('first_name', 'New Hire'))
    if 'name' not in info:
        info['name'] = f"{info.get('first_name','')} {info.get('last_name','')".strip()}
    logger.info(f"[IT Provisioning] Generating IT checklist for {name}")

    provider = os.getenv("PRIMARY_LLM_PROVIDER", "featherless")
    if provider == "featherless":
        llm = ChatOpenAI(
            model=os.getenv("IT_PROVISIONING_MODEL", "meta-llama/Meta-Llama-3.1-8B-Instruct"),
            base_url=os.getenv("FEATHERLESS_BASE_URL", "https://api.featherless.ai/v1"),
            api_key=os.getenv("FEATHERLESS_API_KEY"),
            temperature=0.2,
        )
    else:
        llm = ChatOpenAI(
            model=os.getenv("IT_PROVISIONING_MODEL", "gpt-4o-mini"),
            base_url=os.getenv("AIML_BASE_URL"),
            api_key=os.getenv("AIML_API_KEY"),
        )

    start_date = info.get("start_date", str(datetime.now().date()))

    prompt = f"""
You are an IT Provisioning Specialist. Create a detailed IT setup checklist for:
- Name: {info['name']}
- Role: {info['role']}
- Department: {info['department']}
- Start Date: {start_date}
- Work Mode: {info.get('work_mode', 'hybrid')}

Return a JSON object:
{{
  "accounts": [
    {{"system": "Google Workspace", "email": "...", "status": "pending", "deadline": "Day 1"}},
    {{"system": "Slack", "status": "pending", "deadline": "Day 1"}},
    {{"system": "GitHub", "status": "pending", "deadline": "Day 2"}},
    {{"system": "Jira", "status": "pending", "deadline": "Day 2"}}
  ],
  "equipment": [
    {{"item": "MacBook Pro 14\"", "quantity": 1, "status": "ordered", "delivery": "Day 1"}},
    {{"item": "Monitor", "quantity": 1, "status": "ordered"}}
  ],
  "access_permissions": [
    {{"resource": "GitHub org", "level": "write", "approver": "manager"}},
    {{"resource": "AWS Dev account", "level": "read", "approver": "security_team"}}
  ],
  "software_licenses": [
    {{"tool": "JetBrains IDE", "license_type": "team", "status": "pending"}}
  ],
  "it_notes": "summary of IT setup plan",
  "estimated_completion_date": "YYYY-MM-DD"
}}
Return ONLY valid JSON. Tailor to the role/department.
"""
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        checklist = json.loads(content)
        state["it_checklist"] = checklist
        state["status"] = "checklist_ready"
        logger.success(f"[IT Provisioning] Generated {len(checklist.get('accounts', []))} accounts")
    except Exception as e:
        logger.error(f"[IT Provisioning] LLM error: {e}, using fallback checklist")
        role = info.get('role', 'Employee')
        dept = info.get('department', 'General')
        email = info.get('email', f"{info.get('first_name','user').lower()}@company.com")
        state["it_checklist"] = {
            "accounts": [
                {"system": "Google Workspace", "email": email, "status": "pending", "deadline": "Day 1"},
                {"system": "Slack", "status": "pending", "deadline": "Day 1"},
                {"system": "GitHub", "status": "pending", "deadline": "Day 2"},
                {"system": "Jira", "status": "pending", "deadline": "Day 2"},
                {"system": "Notion", "status": "pending", "deadline": "Day 3"},
                {"system": "Zoom", "status": "pending", "deadline": "Day 1"},
            ],
            "equipment": [
                {"item": 'MacBook Pro 14"' if "Engineer" in role else 'MacBook Air 15"', "quantity": 1, "status": "ordered", "delivery": "Day 1"},
                {"item": "External Monitor" if "Engineer" in role else "iPad", "quantity": 1, "status": "ordered"},
            ],
            "access_permissions": [
                {"resource": f"{dept} shared drive", "level": "write", "approver": "manager"},
                {"resource": "VPN", "level": "standard", "approver": "it_team"},
            ],
            "software_licenses": [
                {"tool": "JetBrains IDE" if "Engineer" in role else "Microsoft Office", "license_type": "team", "status": "pending"},
            ],
            "it_notes": f"Standard {dept} IT setup for {role}. All Day 1 items ready.",
            "estimated_completion_date": "Day 3",
        }
        state["status"] = "checklist_ready"

    return state


async def send_to_band(state: ITProvisioningState) -> ITProvisioningState:
    """Node 2: Send IT checklist to Band room, handoff to Manager Review."""
    if state.get("status") != "checklist_ready":
        return state

    client = BandClient("IT Provisioning Agent")
    checklist = state["it_checklist"]
    info = state["employee_info"]

    accounts_count = len(checklist.get("accounts", []))
    equipment_count = len(checklist.get("equipment", []))

    await client.send_message(
        room_id=state["room_id"],
        message=(
            f"💻 IT PROVISIONING PLAN READY for {info['name']}\n\n"
            f"📧 Accounts to create: {accounts_count}\n"
            f"🖥️ Equipment to order: {equipment_count}\n"
            f"📅 Estimated setup complete: {checklist.get('estimated_completion_date', 'TBD')}\n\n"
            f"Manager Review Agent: All plans are ready for your final approval.\n"
            f"IT Notes: {checklist.get('it_notes', '')}"
        ),
        metadata={
            "event": "it_provisioning_ready",
            "it_checklist": checklist,
            "employee": info,
            "task_plan": state["task_plan"],
            "hr_review": state["hr_review"],
        },
    )

    state["status"] = "handed_off_to_manager"
    logger.success("[IT Provisioning] Handed off to Manager Review Agent via Band ✓")
    return state


# ─── Build the LangGraph ──────────────────────────────────────────────────────
def build_it_graph():
    workflow = StateGraph(ITProvisioningState)

    workflow.add_node("generate_checklist", generate_it_checklist)
    workflow.add_node("send_to_band", send_to_band)

    workflow.set_entry_point("generate_checklist")
    workflow.add_edge("generate_checklist", "send_to_band")
    workflow.add_edge("send_to_band", END)

    return workflow.compile()


# ─── Agent Runner ─────────────────────────────────────────────────────────────
async def run_it_provisioning(
    employee_info: dict, task_plan: list, hr_review: dict, room_id: str
) -> dict:
    """Entry point to run the IT Provisioning Agent."""
    graph = build_it_graph()

    initial_state = ITProvisioningState(
        employee_info=employee_info,
        task_plan=task_plan,
        hr_review=hr_review,
        it_checklist={},
        room_id=room_id,
        status="init",
    )

    result = await graph.ainvoke(initial_state)
    logger.info(f"[IT Provisioning] Final status: {result['status']}")
    return result
