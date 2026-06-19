# Band of Agents — Smart HR Onboarding System

A multi-agent system for the [Band of Agents Hackathon](https://lablab.ai) where 4 specialized AI agents collaborate through Band to automate enterprise HR onboarding workflows.

**Demo:** https://band-of-agents-hackathon-gfzj.vercel.app  
**Repo:** https://github.com/Ashwin-Dev-27/band-of-agents_Hackathon

## Features

- **Multi-Agent Orchestration** — Four agents (Planner, HR Policy, IT Provisioning, Manager Review) collaborate via Band rooms to process new hire onboarding end-to-end
- **Cross-Framework Architecture** — Combines LangGraph, CrewAI, and PydanticAI agents within a single coordinated workflow
- **Real-Time Dashboard** — React frontend with WebSocket updates, live agent status, and session tracking
- **Human-in-the-Loop Approval** — Manager Review agent generates a final report and awaits manager sign-off before completing the workflow
- **Demo Mode** — Runs the full pipeline with smart mock responses, zero API calls required. Switch to live LLMs by toggling DEMO_MODE in settings

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, Vite 8 |
| Backend | FastAPI (Python), WebSockets |
| Agent Framework | LangGraph (Planner, IT), CrewAI (HR Policy), PydanticAI (Manager Review) |
| Coordination | Band / Thenvoi SDK |
| LLM Providers | Featherless AI (primary), AIML API (fallback) |
| Persistence | JSON file storage |

## Agents

| Agent | Framework | Role |
|-------|-----------|------|
| Planner Agent | LangGraph | Parses new hire info, creates onboarding task plan |
| HR Policy Agent | CrewAI | Validates compliance against company HR policies |
| IT Provisioning Agent | LangGraph | Generates IT setup checklist and account provisioning |
| Manager Review Agent | PydanticAI | Synthesizes final report, requests human approval |

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Band account + API key (required only for live mode)

### Setup

```bash
# Clone the repo
git clone https://github.com/Ashwin-Dev-27/band-of-agents_Hackathon.git
cd band-of-agents_Hackathon

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt

# Copy and fill in environment variables
cp .env.example .env
# Edit .env with your API keys

# Install frontend dependencies
cd frontend
npm install
cd ..
```

### Running

```bash
# Terminal 1: Start backend
uvicorn backend.main:app --reload --port 8000

# Terminal 2: Start frontend
cd frontend && npm run dev
```

Open http://localhost:5173 to see the dashboard.

### Demo Mode

The system runs in demo mode by default (DEMO_MODE=true in .env). In this mode, all 4 agents execute the full pipeline with realistic mock responses — no API keys or LLM calls needed. Toggle demo mode off in the dashboard Settings or set DEMO_MODE=false in .env to use real LLMs.

## Project Structure

```
├── agents/
│   ├── planner_agent.py           # LangGraph — task planning
│   ├── hr_policy_agent.py         # CrewAI — policy compliance
│   ├── it_provisioning_agent.py   # LangGraph — IT setup
│   └── manager_review_agent.py    # PydanticAI — final approval
├── band_integration/
│   ├── band_client.py             # Band SDK wrapper
│   └── room_manager.py            # Manages Band rooms per session
├── backend/
│   └── main.py                    # FastAPI server
├── frontend/                      # React dashboard
├── data/
│   └── hr_policies.txt            # Sample HR policy documents
├── .env.example
├── requirements.txt
└── README.md
```

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Root health check |
| GET | `/health` | Detailed health status and active agents |
| POST | `/api/onboard` | Start onboarding pipeline |
| POST | `/api/approve` | Approve or reject onboarding (human-in-the-loop) |
| GET | `/api/rooms` | List all onboarding sessions |
| GET | `/api/rooms/{room_id}` | Get session details |
| POST | `/api/settings` | Update environment settings |
| WS | `/ws` | Real-time dashboard updates |

## Architecture

```
React Dashboard <--> FastAPI Backend <--> Band SDK <--> 4 AI Agents
                                                        (LangGraph / CrewAI / PydanticAI)
                               |
                         data/sessions.json
```

Each onboarding session creates a dedicated Band room. Agents communicate through this room, sharing structured context and handing off tasks sequentially. The Manager Review agent awaits human approval before completing the workflow.

## License

MIT
