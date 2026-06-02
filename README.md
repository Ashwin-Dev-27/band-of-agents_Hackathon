# 🤖 Band of Agents — Smart HR Onboarding System

A multi-agent system built for the [Band of Agents Hackathon](https://lablab.ai) where 4 specialized AI agents collaborate through Band to automate enterprise HR onboarding workflows.

## 🧠 Agents
| Agent | Framework | Role |
|-------|-----------|------|
| **Planner Agent** | LangGraph | Parses new hire info → creates onboarding task plan |
| **HR Policy Agent** | CrewAI | Answers policy questions, validates compliance |
| **IT Provisioning Agent** | LangGraph | Generates IT setup checklist, account creation |
| **Manager Review Agent** | PydanticAI | Final review + human-in-the-loop approval via Band |

## 🏗️ Architecture
All agents communicate through **Band** as the central coordination layer. Each onboarding session creates a dedicated Band room where agents hand off tasks, share context, and coordinate decisions.

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Band account + API key (band.ai)

### Setup
```bash
# Clone the repo
git clone https://github.com/Ashwin-Dev-27/band-of-agents-hackathon.git
cd band-of-agents-hackathon

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

## 📁 Project Structure
```
├── agents/
│   ├── planner_agent.py        # LangGraph — task planning
│   ├── hr_policy_agent.py      # CrewAI — policy compliance
│   ├── it_provisioning_agent.py # LangGraph — IT setup
│   └── manager_review_agent.py  # PydanticAI — final approval
├── band_integration/
│   ├── band_client.py          # Band SDK wrapper
│   └── room_manager.py         # Manages Band rooms per session
├── backend/
│   └── main.py                 # FastAPI server
├── frontend/                   # React dashboard
├── data/
│   └── hr_policies.txt         # Sample HR policy docs
├── .env.example
├── requirements.txt
└── README.md
```

## 🔑 Environment Variables
```
BAND_API_KEY=your_band_api_key
AIML_API_KEY=your_aiml_api_key
FEATHERLESS_API_KEY=your_featherless_api_key
OPENAI_API_KEY=optional_fallback
```

## 🏆 Hackathon
- **Event**: Band of Agents Hackathon on lablab.ai
- **Track**: Track 1 — Internal Enterprise Workflows
- **Team**: Ashwin Kumar

## 📄 License
MIT
