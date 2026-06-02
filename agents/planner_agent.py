"""
Planner Agent — LangGraph-based agent
Role: Parse new hire information and create a structured onboarding task plan.
Then hands off to HR Policy Agent via Band.
"""
import os
import json
from typing import TypedDict, Annotated
from dotenv import load_dotenv
from loguru import logger

# LangGraph imports
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from band_integration.band_client import BandClient

load_dotenv()


# ─── LLM Factory ───────────────────────────────────────────────────────────────────
def get_llm(model_env_var: str = "PLANNER_MODEL") -> ChatOpenAI:
    """
    Returns a ChatOpenAI-compatible client pointed at Featherless (primary, confirmed working)
    or AIML API (fallback when credits are available).
    """
    provider = os.getenv("PRIMARY_LLM_PROVIDER", "featherless")
    model = os.getenv(model_env_var, "meta-llama/Meta-Llama-3.1-8B-Instruct")

    if provider == "featherless":
        return ChatOpenAI(
            model=model,
            base_url=os.getenv("FEATHERLESS_BASE_URL", "https://api.featherless.ai/v1"),
            api_key=os.getenv("FEATHERLESS_API_KEY"),
            temperature=0.3,
        )
    else:  # aimlapi
        return ChatOpenAI(
            model=model,
            base_url=os.getenv("AIML_BASE_URL", "https://api.aimlapi.com/v1"),
            api_key=os.getenv("AIML_API_KEY"),
            temperature=0.3,
        )



# ─── State Definition ───────────────────────────────────────────────────────────────────
class PlannerState(TypedDict):
    employee_info: dict
    task_plan: list
    room_id: str
    messages: list
    status: str


# ─── LangGraph Nodes ───────────────────────────────────────────────────────────────────
def parse_employee_info(state: PlannerState) -> PlannerState:
    """Node 1: Parse and validate new hire information."""
    info = state["employee_info"]
    # Support both 'name' and 'first_name'+'last_name' from frontend form
    if "name" not in info and ("first_name" in info or "last_name" in info):
        info["name"] = f"{info.get('first_name', '')} {info.get('last_name', '')}".strip()
    logger.info(f"[Planner] Parsing employee info for: {info.get('name', 'Unknown')}")
    state["status"] = "parsed"
    return state



def generate_task_plan(state: PlannerState) -> PlannerState:
    """Node 2: Use LLM to generate a detailed onboarding task plan."""
    if "incomplete" in state.get("status", ""):
        return state

    info = state["employee_info"]
    logger.info("[Planner] Generating task plan via Featherless LLM...")

    try:
        llm = get_llm("PLANNER_MODEL")

        prompt = f"""You are an HR Onboarding Planner. Create a structured onboarding task plan for:
- Name: {info.get('name', 'New Hire')}
- Role: {info.get('role', 'Unknown')}
- Department: {info.get('department', 'Unknown')}
- Start Date: {info.get('start_date', 'TBD')}
- Manager: {info.get('manager_email', info.get('manager', 'TBD'))}

Generate a JSON array of exactly 8 onboarding tasks. Use this structure:
[{{"task_id": "T001", "category": "HR", "title": "Task title", "description": "What needs to be done", "assignee": "hr_agent", "priority": "high", "deadline_days": 1}}]

Return ONLY a valid JSON array, no markdown, no explanation."""

        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content.strip()

        # Strip markdown code fences if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        tasks = json.loads(content)
        state["task_plan"] = tasks
        state["status"] = "plan_ready"
        logger.success(f"[Planner] Generated {len(tasks)} tasks via Featherless")

    except Exception as e:
        logger.error(f"[Planner] LLM error: {e}, using fallback plan")
        # Intelligent fallback plan based on role/dept
        role = info.get('role', 'Employee')
        dept = info.get('department', 'General')
        state["task_plan"] = [
            {"task_id": "T001", "category": "HR", "title": "Complete onboarding paperwork", "description": "Sign NDA, employment contract, tax forms", "assignee": "hr_agent", "priority": "high", "deadline_days": 1},
            {"task_id": "T002", "category": "IT", "title": "Create email account", "description": f"Set up {info.get('email', 'work email')}", "assignee": "it_agent", "priority": "high", "deadline_days": 1},
            {"task_id": "T003", "category": "IT", "title": "Provision laptop and equipment", "description": f"Order and configure equipment for {role}", "assignee": "it_agent", "priority": "high", "deadline_days": 2},
            {"task_id": "T004", "category": "HR", "title": "Benefits enrollment", "description": "Health insurance, 401k enrollment", "assignee": "hr_agent", "priority": "medium", "deadline_days": 30},
            {"task_id": "T005", "category": "Manager", "title": "Manager introduction meeting", "description": f"30-min intro call with manager to discuss {role} expectations", "assignee": "manager", "priority": "high", "deadline_days": 1},
            {"task_id": "T006", "category": "IT", "title": f"Set up {dept} tools access", "description": f"Grant access to {dept}-specific software and systems", "assignee": "it_agent", "priority": "high", "deadline_days": 2},
            {"task_id": "T007", "category": "HR", "title": "Compliance training", "description": "Complete mandatory compliance and security training", "assignee": "hr_agent", "priority": "high", "deadline_days": 30},
            {"task_id": "T008", "category": "Manager", "title": "30-day check-in", "description": "First performance check-in with manager", "assignee": "manager", "priority": "medium", "deadline_days": 30},
        ]
        state["status"] = "plan_ready"

    return state



async def handoff_to_band(state: PlannerState) -> PlannerState:
    """Node 3: Send the plan to Band room and notify HR Policy Agent."""
    if state.get("status") != "plan_ready":
        return state

    client = BandClient("Planner Agent")

    message = (
        f"📋 ONBOARDING PLAN READY for {state['employee_info']['name']}\n\n"
        f"Generated {len(state['task_plan'])} tasks.\n\n"
        f"HR Policy Agent: Please review for policy compliance.\n"
        f"Task data attached in metadata."
    )

    await client.send_message(
        room_id=state["room_id"],
        message=message,
        metadata={
            "event": "plan_ready",
            "task_plan": state["task_plan"],
            "employee": state["employee_info"],
        },
    )

    state["status"] = "handed_off_to_hr"
    logger.success("[Planner] Handed off to HR Policy Agent via Band ✓")
    return state


# ─── Build the LangGraph ──────────────────────────────────────────────────────
def build_planner_graph():
    workflow = StateGraph(PlannerState)

    workflow.add_node("parse_info", parse_employee_info)
    workflow.add_node("generate_plan", generate_task_plan)
    workflow.add_node("handoff_to_band", handoff_to_band)

    workflow.set_entry_point("parse_info")
    workflow.add_edge("parse_info", "generate_plan")
    workflow.add_edge("generate_plan", "handoff_to_band")
    workflow.add_edge("handoff_to_band", END)

    return workflow.compile(checkpointer=InMemorySaver())


# ─── Agent Runner ─────────────────────────────────────────────────────────────
async def run_planner(employee_info: dict, room_id: str) -> dict:
    """Entry point to run the Planner Agent."""
    graph = build_planner_graph()

    initial_state = PlannerState(
        employee_info=employee_info,
        task_plan=[],
        room_id=room_id,
        messages=[],
        status="init",
    )

    config = {"configurable": {"thread_id": room_id}}
    result = await graph.ainvoke(initial_state, config=config)

    logger.info(f"[Planner] Final status: {result['status']}")
    return result
