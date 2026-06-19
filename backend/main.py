"""
FastAPI Backend — Orchestrates the multi-agent onboarding workflow.

DEMO MODE (active until Jun 11 when hackathon API credits unlock):
  - All 4 agents run with smart mock responses — no LLM calls needed
  - Full pipeline simulation with realistic timing and Band messages
  - Flip DEMO_MODE=false in .env on Jun 11 to use real LLMs

LIVE MODE (Jun 11+):
  - Agent 1 (Planner)   → LangGraph  + Featherless/AIML
  - Agent 2 (HR Policy) → CrewAI     + Featherless/AIML
  - Agent 3 (IT Prov.)  → LangGraph  + Featherless/AIML
  - Agent 4 (Mgr Rev.)  → PydanticAI + Featherless/AIML
  - All coordinated via Band/Thenvoi rooms
"""
import os
import json
import asyncio
import uuid
from contextlib import asynccontextmanager
from typing import Optional
from datetime import datetime, date
from dotenv import load_dotenv
from loguru import logger
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() != "false"


@asynccontextmanager
async def lifespan(app: FastAPI):
    mode = "DEMO MODE — smart mock responses active" if DEMO_MODE else "LIVE MODE — real LLMs active"
    logger.info(f"Band of Agents HR Onboarding System — {mode}")
    logger.success("Server ready ✓  http://localhost:8000")
    yield


app = FastAPI(
    title="Band of Agents — HR Onboarding System",
    description="Multi-agent HR onboarding system using Band as the coordination layer",
    version="1.0.0",
    lifespan=lifespan,
)

cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# JSON file session store for persistence
SESSIONS_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "sessions.json")

def load_sessions() -> dict:
    if os.path.exists(SESSIONS_FILE):
        try:
            with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading sessions: {e}")
    return {}

def save_sessions():
    try:
        os.makedirs(os.path.dirname(SESSIONS_FILE), exist_ok=True)
        with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(sessions, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving sessions: {e}")

sessions: dict[str, dict] = load_sessions()

# WebSocket connections for live dashboard updates
websocket_clients: list[WebSocket] = []


class NewHireRequest(BaseModel):
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    department: str = ""
    role: str = ""
    start_date: Optional[str] = ""
    manager_email: Optional[str] = ""
    employment_type: Optional[str] = "full-time"
    name: Optional[str] = None
    manager: Optional[str] = None
    work_mode: Optional[str] = "hybrid"

    def get_full_name(self) -> str:
        if self.name:
            return self.name
        return f"{self.first_name} {self.last_name}".strip() or "New Hire"

    def to_agent_dict(self) -> dict:
        return {
            "name": self.get_full_name(),
            "first_name": self.first_name,
            "last_name": self.last_name,
            "email": self.email,
            "department": self.department,
            "role": self.role,
            "start_date": self.start_date or str(date.today()),
            "manager": self.manager or self.manager_email or "Hiring Manager",
            "manager_email": self.manager_email or "",
            "employment_type": self.employment_type or "full-time",
            "work_mode": self.work_mode or "hybrid",
        }


class ApprovalRequest(BaseModel):
    room_id: str
    decision: Optional[str] = "approve"   # "approve" or "reject"
    approved: Optional[bool] = None        # legacy field
    approver: Optional[str] = "Manager"
    notes: Optional[str] = ""


class SettingsRequest(BaseModel):
    DEMO_MODE: bool
    BAND_API_KEY: str
    AIML_API_KEY: str
    FEATHERLESS_API_KEY: str


async def broadcast(message: dict):
    if message.get("type") in ["new_session", "session_update"]:
        save_sessions()

    dead = []
    for ws in websocket_clients:
        try:
            await ws.send_json(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in websocket_clients:
            websocket_clients.remove(ws)


@app.get("/")
async def root():
    return {
        "message": "Band of Agents — HR Onboarding System",
        "status": "running",
        "mode": "DEMO (credits unlock Jun 11)" if DEMO_MODE else "LIVE",
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "demo_mode": DEMO_MODE,
        "agents": ["Planner (LangGraph)", "HR Policy (CrewAI)", "IT Provisioning (LangGraph)", "Manager Review (PydanticAI)"],
    }


@app.post("/api/settings")
async def update_settings(request: SettingsRequest):
    env_file = os.path.join(os.path.dirname(__file__), "..", ".env")
    lines = []
    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
    updates = {
        "DEMO_MODE": str(request.DEMO_MODE).lower(),
        "BAND_API_KEY": request.BAND_API_KEY,
        "AIML_API_KEY": request.AIML_API_KEY,
        "FEATHERLESS_API_KEY": request.FEATHERLESS_API_KEY,
    }
    
    # Auto-detect PRIMARY_LLM_PROVIDER based on provided keys
    if request.AIML_API_KEY and not request.FEATHERLESS_API_KEY:
        updates["PRIMARY_LLM_PROVIDER"] = "aimlapi"
    elif request.FEATHERLESS_API_KEY:
        updates["PRIMARY_LLM_PROVIDER"] = "featherless"
        
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            new_lines.append(line.rstrip("\n"))
            continue
        key = stripped.split("=")[0].strip()
        if key in updates:
            new_lines.append(f"{key}={updates.pop(key)}")
        else:
            new_lines.append(line.rstrip("\n"))
            
    for k, v in updates.items():
        new_lines.append(f"{k}={v}")
        
    with open(env_file, "w", encoding="utf-8") as f:
        f.write("\n".join(new_lines) + "\n")
        
    return {"status": "success", "message": "Settings updated."}


@app.post("/api/onboard")
async def start_onboarding(request: NewHireRequest):
    """
    Trigger the 4-agent onboarding pipeline.
    Demo mode: smart mock responses, full simulation.
    Live mode (Jun 11+): real LLM calls via Featherless/AIML.
    """
    info = request.to_agent_dict()
    room_id = f"band_{uuid.uuid4().hex[:10]}"
    logger.info(f"[API] Starting onboarding for {info['name']} | room: {room_id} | mode: {'DEMO' if DEMO_MODE else 'LIVE'}")

    # Store session
    sessions[room_id] = {
        "room_id": room_id,
        "employee_name": info["name"],
        "department": info["department"],
        "role": info["role"],
        "email": info["email"],
        "status": "running",
        "progress": 0,
        "start_time": datetime.utcnow().isoformat(),
        "agents": [
            {"name": "Planner", "status": "active", "framework": "LangGraph", "output": ""},
            {"name": "HR Policy", "status": "waiting", "framework": "CrewAI", "output": ""},
            {"name": "IT Provisioning", "status": "waiting", "framework": "LangGraph", "output": ""},
            {"name": "Manager Review", "status": "waiting", "framework": "PydanticAI", "output": ""},
        ],
        "messages": [],
        "report": None,
        "info": info,
    }

    # Broadcast session created
    await broadcast({"type": "new_session", "data": sessions[room_id]})

    # Run pipeline in background
    asyncio.create_task(_run_pipeline(room_id, info))

    return {
        "status": "started",
        "room_id": room_id,
        "mode": "demo" if DEMO_MODE else "live",
        "message": f"Onboarding pipeline started for {info['name']} in Band room {room_id}",
    }


async def _run_pipeline(room_id: str, info: dict):
    """
    Full 4-agent pipeline.
    Demo mode: simulates realistic agent behavior with smart responses.
    Live mode: calls real LLMs via LangGraph/CrewAI/PydanticAI.
    """
    try:
        if DEMO_MODE:
            await _run_demo_pipeline(room_id, info)
        else:
            await _run_live_pipeline(room_id, info)
    except Exception as e:
        logger.error(f"Pipeline error for {room_id}: {e}")
        await broadcast({"type": "error", "room_id": room_id, "error": str(e)})


async def _run_demo_pipeline(room_id: str, info: dict):
    """Smart demo pipeline — realistic responses, zero API calls."""
    name = info["name"]
    role = info["role"]
    dept = info["department"]
    email = info.get("email", f"{info.get('first_name','user').lower()}@company.com")

    def update(agent_idx, status, output, progress, session_status=None):
        s = sessions[room_id]
        s["agents"][agent_idx]["status"] = status
        s["agents"][agent_idx]["output"] = output
        s["progress"] = progress
        if session_status:
            s["status"] = session_status
        # Activate next agent
        if status == "done" and agent_idx < 3:
            s["agents"][agent_idx + 1]["status"] = "active"
        return s

    def add_message(agent, text):
        from datetime import datetime
        sessions[room_id]["messages"].append({
            "agent": agent,
            "text": text,
            "ts": datetime.now().strftime("%H:%M"),
        })

    # ── Agent 1: Planner (LangGraph) ─────────────────────────────────────────
    await asyncio.sleep(1.5)
    add_message("Planner", f"📋 Generating onboarding plan for {name} ({role}, {dept})...")
    await broadcast({"type": "session_update", "room_id": room_id, "data": sessions[room_id]})

    await asyncio.sleep(2.5)
    task_plan = _generate_demo_task_plan(info)
    s = update(0, "done", f"Generated {len(task_plan)}-task onboarding plan ✓", 25)
    add_message("Planner", f"✅ Plan ready: {len(task_plan)} tasks across 4 weeks. Handing off to HR Policy Agent via Band.")
    sessions[room_id]["task_plan"] = task_plan
    await broadcast({"type": "session_update", "room_id": room_id, "data": sessions[room_id]})

    # ── Agent 2: HR Policy (CrewAI) ──────────────────────────────────────────
    await asyncio.sleep(1.5)
    add_message("HR Policy", f"🔍 Reviewing {name}'s onboarding plan against company HR policies...")
    await broadcast({"type": "session_update", "room_id": room_id, "data": sessions[room_id]})

    await asyncio.sleep(3)
    hr_review = _generate_demo_hr_review(info, task_plan)
    score = hr_review["compliance_score"]
    s = update(1, "done", f"Compliance score: {score}/100 ✓", 50)
    add_message("HR Policy", f"✅ Compliance review complete. Score: {score}/100. "
                             f"{len(hr_review['missing_tasks'])} recommendations. "
                             f"Passing to IT Provisioning Agent.")
    sessions[room_id]["hr_review"] = hr_review
    await broadcast({"type": "session_update", "room_id": room_id, "data": sessions[room_id]})

    # ── Agent 3: IT Provisioning (LangGraph) ─────────────────────────────────
    await asyncio.sleep(1.5)
    add_message("IT Provisioning", f"💻 Setting up IT accounts and equipment for {name}...")
    await broadcast({"type": "session_update", "room_id": room_id, "data": sessions[room_id]})

    await asyncio.sleep(2.5)
    it_checklist = _generate_demo_it_checklist(info)
    acct_count = len(it_checklist["accounts"])
    equip_count = len(it_checklist["equipment"])
    s = update(2, "done", f"{acct_count} accounts + {equip_count} devices provisioned ✓", 75)
    add_message("IT Provisioning",
                f"✅ IT setup complete. {acct_count} accounts queued, {equip_count} devices ordered. "
                f"Handing to Manager Review Agent for final approval.")
    sessions[room_id]["it_checklist"] = it_checklist
    await broadcast({"type": "session_update", "room_id": room_id, "data": sessions[room_id]})

    # ── Agent 4: Manager Review (PydanticAI) ─────────────────────────────────
    await asyncio.sleep(1.5)
    add_message("Manager Review", f"👔 Synthesizing full onboarding report for {name}...")
    await broadcast({"type": "session_update", "room_id": room_id, "data": sessions[room_id]})

    await asyncio.sleep(2)
    report = _generate_demo_report(info, task_plan, hr_review, it_checklist)
    s = update(3, "pending", "Report ready — awaiting manager approval", 75, "pending_approval")
    sessions[room_id]["report"] = report
    add_message("Manager Review",
                f"⏳ Onboarding report ready for {name}.\n"
                f"HR compliance: {hr_review['compliance_score']}/100 | "
                f"Accounts: {acct_count} | Equipment: {equip_count}\n"
                f"AWAITING manager approval via this Band room.")
    await broadcast({"type": "session_update", "room_id": room_id, "data": sessions[room_id]})
    logger.success(f"[Demo] Pipeline complete for {room_id}. Awaiting approval.")


async def _run_live_pipeline(room_id: str, info: dict):
    """Live pipeline with real LLM calls via Featherless/AIML."""
    try:
        from agents.planner_agent import run_planner
        from agents.hr_policy_agent import run_hr_policy_agent
        from agents.it_provisioning_agent import run_it_provisioning
        from agents.manager_review_agent import run_manager_review

        await broadcast({"type": "agent_started", "agent": "Planner", "room_id": room_id})
        planner_result = await run_planner(info, room_id)
        task_plan = planner_result.get("task_plan", [])
        sessions[room_id]["task_plan"] = task_plan
        sessions[room_id]["progress"] = 25
        sessions[room_id]["agents"][0] = {"name": "Planner", "status": "done", "framework": "LangGraph", "output": f"Generated {len(task_plan)} tasks"}
        sessions[room_id]["agents"][1]["status"] = "active"
        await broadcast({"type": "session_update", "room_id": room_id, "data": sessions[room_id]})

        await broadcast({"type": "agent_started", "agent": "HR Policy", "room_id": room_id})
        hr_review = await run_hr_policy_agent(task_plan, info, room_id)
        sessions[room_id]["hr_review"] = hr_review
        sessions[room_id]["progress"] = 50
        sessions[room_id]["agents"][1] = {"name": "HR Policy", "status": "done", "framework": "CrewAI", "output": f"Score: {hr_review.get('compliance_score', 85)}/100"}
        sessions[room_id]["agents"][2]["status"] = "active"
        await broadcast({"type": "session_update", "room_id": room_id, "data": sessions[room_id]})

        await broadcast({"type": "agent_started", "agent": "IT Provisioning", "room_id": room_id})
        it_result = await run_it_provisioning(info, task_plan, hr_review, room_id)
        it_checklist = it_result.get("it_checklist", {})
        sessions[room_id]["it_checklist"] = it_checklist
        sessions[room_id]["progress"] = 75
        sessions[room_id]["agents"][2] = {"name": "IT Provisioning", "status": "done", "framework": "LangGraph", "output": f"{len(it_checklist.get('accounts', []))} accounts provisioned"}
        sessions[room_id]["agents"][3]["status"] = "active"
        await broadcast({"type": "session_update", "room_id": room_id, "data": sessions[room_id]})

        await broadcast({"type": "agent_started", "agent": "Manager Review", "room_id": room_id})
        manager_result = await run_manager_review(info, task_plan, hr_review, it_checklist, room_id)
        sessions[room_id]["report"] = manager_result.get("report")
        sessions[room_id]["progress"] = 75
        sessions[room_id]["status"] = "pending_approval"
        sessions[room_id]["agents"][3] = {"name": "Manager Review", "status": "pending", "framework": "PydanticAI", "output": "Awaiting manager approval"}
        await broadcast({"type": "session_update", "room_id": room_id, "data": sessions[room_id]})

    except Exception as e:
        logger.error(f"Live pipeline error: {e}")
        raise


def _generate_demo_task_plan(info: dict) -> list:
    role = info.get("role", "Employee")
    dept = info.get("department", "General")
    name = info.get("name", "New Hire")
    return [
        {"task_id": "T001", "category": "HR", "title": "Complete onboarding paperwork", "description": "Sign NDA, employment contract, I-9, tax forms", "assignee": "hr_agent", "priority": "high", "deadline_days": 1},
        {"task_id": "T002", "category": "IT", "title": "Create email & accounts", "description": f"Set up work email {info.get('email', '')} and core accounts", "assignee": "it_agent", "priority": "high", "deadline_days": 1},
        {"task_id": "T003", "category": "IT", "title": "Provision equipment", "description": f"Configure {'MacBook Pro + dual monitors' if 'Engineer' in role else 'MacBook Air + monitor'} for {name}", "assignee": "it_agent", "priority": "high", "deadline_days": 2},
        {"task_id": "T004", "category": "Manager", "title": "Manager introduction meeting", "description": f"30-minute kick-off call covering {role} expectations, team norms, 90-day plan", "assignee": "manager", "priority": "high", "deadline_days": 1},
        {"task_id": "T005", "category": "IT", "title": f"Set up {dept} tool access", "description": f"Grant access to {dept}-specific systems, repos, and dashboards", "assignee": "it_agent", "priority": "high", "deadline_days": 2},
        {"task_id": "T006", "category": "HR", "title": "Benefits enrollment", "description": "Health insurance, dental, 401k, and PTO orientation", "assignee": "hr_agent", "priority": "medium", "deadline_days": 30},
        {"task_id": "T007", "category": "HR", "title": "Security & compliance training", "description": "Complete mandatory security awareness and compliance modules", "assignee": "hr_agent", "priority": "high", "deadline_days": 30},
        {"task_id": "T008", "category": "Manager", "title": "30-day check-in", "description": "First performance touchpoint — celebrate wins, address challenges", "assignee": "manager", "priority": "medium", "deadline_days": 30},
        {"task_id": "T009", "category": "Manager", "title": "Team introduction", "description": f"Introduce {name} to the {dept} team and key stakeholders", "assignee": "manager", "priority": "high", "deadline_days": 1},
        {"task_id": "T010", "category": "HR", "title": "90-day performance review", "description": "Formal review of onboarding progress and role fit", "assignee": "hr_agent", "priority": "medium", "deadline_days": 90},
    ]


def _generate_demo_hr_review(info: dict, task_plan: list) -> dict:
    role = info.get("role", "Employee")
    dept = info.get("department", "General")
    employment_type = info.get("employment_type", "full-time")
    score = 91 if employment_type == "full-time" else 86
    return {
        "compliance_score": score,
        "approved": True,
        "violations": [],
        "missing_tasks": [
            "Add benefits enrollment reminder for Day 30",
            "Include remote-work addendum if applicable",
        ],
        "recommendations": [
            f"Schedule compliance training within first week for {role}",
            "Confirm NDA signed before Day 1",
            f"Set up dedicated {dept} team Slack channel introduction",
        ],
        "hr_notes": (
            f"Onboarding plan for {info['name']} is {score}% compliant with company HR policies. "
            f"No critical violations found. {2} minor recommendations added. "
            f"Plan is approved for IT provisioning."
        ),
    }


def _generate_demo_it_checklist(info: dict) -> dict:
    role = info.get("role", "Employee")
    dept = info.get("department", "General")
    email = info.get("email", f"{info.get('first_name', 'user').lower()}@company.com")
    is_engineer = "Engineer" in role or "Dev" in role or "Data" in role
    return {
        "accounts": [
            {"system": "Google Workspace", "email": email, "status": "pending", "deadline": "Day 1"},
            {"system": "Slack", "status": "pending", "deadline": "Day 1"},
            {"system": "GitHub", "status": "pending", "deadline": "Day 2"},
            {"system": "Jira", "status": "pending", "deadline": "Day 2"},
            {"system": "Notion", "status": "pending", "deadline": "Day 3"},
            {"system": "Zoom", "status": "pending", "deadline": "Day 1"},
            {"system": "1Password", "status": "pending", "deadline": "Day 1"},
            {"system": "AWS Console (Dev)" if is_engineer else "Salesforce", "status": "pending", "deadline": "Day 3"},
        ],
        "equipment": [
            {"item": 'MacBook Pro 14" M3' if is_engineer else 'MacBook Air 15" M3', "quantity": 1, "status": "ordered", "delivery": "Day 1"},
            {"item": "27\" External Monitor" if is_engineer else "iPad Pro 11\"", "quantity": 1, "status": "ordered", "delivery": "Day 2"},
            {"item": "Ergonomic Chair + Desk Setup" if info.get("work_mode") == "remote" else "Logitech Keyboard & Mouse", "quantity": 1, "status": "ordered"},
        ],
        "access_permissions": [
            {"resource": f"{dept} GitHub repos", "level": "write" if is_engineer else "read", "approver": "manager"},
            {"resource": "VPN", "level": "standard", "approver": "it_team"},
            {"resource": f"{dept} Notion workspace", "level": "editor", "approver": "manager"},
            {"resource": "AWS Dev account" if is_engineer else "Analytics Dashboard", "level": "read", "approver": "security_team"},
        ],
        "software_licenses": [
            {"tool": "JetBrains IDE Suite" if is_engineer else "Microsoft Office 365", "license_type": "team", "status": "pending"},
            {"tool": "Figma" if "Design" in dept or "Product" in role else "Slack Pro", "license_type": "team", "status": "pending"},
        ],
        "it_notes": f"Standard {dept} IT setup for {role}. All Day 1 critical items ready. Equipment ships 2 business days before start date.",
        "estimated_completion_date": "Day 3",
    }


def _generate_demo_report(info: dict, task_plan: list, hr_review: dict, it_checklist: dict) -> dict:
    return {
        "employee_name": info["name"],
        "employee_role": info["role"],
        "employee_department": info["department"],
        "start_date": info.get("start_date", "TBD"),
        "manager": info.get("manager", "Hiring Manager"),
        "total_tasks": len(task_plan),
        "hr_compliance_score": hr_review["compliance_score"],
        "hr_approved": hr_review["approved"],
        "accounts_to_create": len(it_checklist["accounts"]),
        "equipment_to_order": len(it_checklist["equipment"]),
        "accounts": [a["system"] for a in it_checklist["accounts"]],
        "equipment": [e["item"] for e in it_checklist["equipment"]],
        "access": [a["resource"] for a in it_checklist["access_permissions"]],
        "planner_summary": f"Generated {len(task_plan)}-task onboarding plan covering HR, IT, Manager, and Legal tracks across 90 days.",
        "hr_summary": hr_review["hr_notes"],
        "it_summary": it_checklist["it_notes"],
        "overall_status": "APPROVED",
        "priority_actions": [
            f"Create {info.get('email', 'work email')} — needed before Day 1",
            "Order and configure laptop — ship 2 days before start",
            "Schedule intro meeting with manager — Day 1",
            "Enroll in benefits within 30 days",
        ],
        "manager_notes": (
            f"Onboarding package for {info['name']} is complete and ready for your approval.\n"
            f"HR compliance score: {hr_review['compliance_score']}/100. No violations.\n"
            f"IT: {len(it_checklist['accounts'])} accounts + {len(it_checklist['equipment'])} devices ready.\n"
            f"All Day 1 critical items are in place. Awaiting your signature."
        ),
        "report_generated_at": datetime.utcnow().isoformat(),
        "approved": False,
    }


@app.post("/api/approve")
async def approve_onboarding(request: ApprovalRequest):
    """Human-in-the-loop: Manager approves or rejects the onboarding plan."""
    session = sessions.get(request.room_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Support both decision="approve" and approved=True
    is_approved = (request.decision == "approve") or (request.approved is True)
    decision_str = "APPROVED" if is_approved else "REJECTED"

    session["status"] = "completed" if is_approved else "failed"
    session["progress"] = 100 if is_approved else session["progress"]
    session["agents"][3]["status"] = "done" if is_approved else "error"
    session["agents"][3]["output"] = f"✅ {decision_str} by {request.approver}"

    if session.get("report"):
        session["report"]["approved"] = is_approved
        session["report"]["approved_by"] = request.approver
        session["report"]["approved_at"] = datetime.utcnow().isoformat()

    from datetime import datetime as dt
    session["messages"].append({
        "agent": "Manager Review",
        "text": f"{'✅ APPROVED' if is_approved else '❌ REJECTED'} by {request.approver}. "
                f"{'Welcome to the team! 🎉' if is_approved else 'Onboarding placed on hold.'}",
        "ts": dt.now().strftime("%H:%M"),
    })

    await broadcast({"type": "session_update", "room_id": request.room_id, "data": session})
    logger.info(f"[API] {decision_str} onboarding for {session['employee_name']} by {request.approver}")

    return {"status": "recorded", "decision": decision_str, "room_id": request.room_id}


@app.get("/api/rooms")
async def get_rooms():
    return {"rooms": list(sessions.values()), "count": len(sessions)}


@app.get("/api/rooms/{room_id}")
async def get_room(room_id: str):
    session = sessions.get(room_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    websocket_clients.append(websocket)
    logger.info("Dashboard WebSocket client connected")

    # Send current sessions on connect
    try:
        await websocket.send_json({
            "type": "init",
            "sessions": list(sessions.values()),
            "mode": "demo" if DEMO_MODE else "live",
        })
    except Exception:
        pass

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in websocket_clients:
            websocket_clients.remove(websocket)
        logger.info("Dashboard WebSocket client disconnected")


@app.on_event("startup")
async def startup():
    mode = "DEMO MODE — smart mock responses active (credits unlock Jun 11)" if DEMO_MODE else "LIVE MODE — real LLMs active"
    logger.info(f"Band of Agents HR Onboarding System — {mode}")
    logger.success("Server ready ✓  http://localhost:8000")

frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
    logger.info(f"Serving frontend from {frontend_dist}")
