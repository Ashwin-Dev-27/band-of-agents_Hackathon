"""
Room Manager — Manages Band collaboration rooms for onboarding sessions.
Each new hire gets their own room where all 4 agents collaborate.
"""
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from loguru import logger
from band_integration.band_client import BandClient


class OnboardingRoom:
    """Represents a single onboarding session's Band room."""

    def __init__(self, room_id: str, employee_name: str):
        self.room_id = room_id
        self.employee_name = employee_name
        self.created_at = datetime.utcnow()
        self.messages: List[dict] = []
        self.status = "active"  # active | pending_approval | completed

    def add_message(self, agent: str, message: str, metadata: dict = None):
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "agent": agent,
            "message": message,
            "metadata": metadata or {},
        }
        self.messages.append(entry)
        return entry

    def to_dict(self):
        return {
            "room_id": self.room_id,
            "employee_name": self.employee_name,
            "created_at": self.created_at.isoformat(),
            "status": self.status,
            "message_count": len(self.messages),
            "messages": self.messages,
        }


class RoomManager:
    """
    Manages all active onboarding Band rooms.
    The orchestrator calls this to create rooms and coordinate agents.
    """

    def __init__(self):
        self.rooms: Dict[str, OnboardingRoom] = {}
        # Each agent gets its own Band client
        self.planner_client = BandClient("Planner Agent")
        self.hr_client = BandClient("HR Policy Agent")
        self.it_client = BandClient("IT Provisioning Agent")
        self.manager_client = BandClient("Manager Review Agent")

    async def connect_all_agents(self):
        """Connect all 4 agents to Band platform."""
        logger.info("Connecting all agents to Band...")
        await asyncio.gather(
            self.planner_client.connect(),
            self.hr_client.connect(),
            self.it_client.connect(),
            self.manager_client.connect(),
        )
        logger.success("All agents connected to Band ✓")

    async def create_onboarding_room(self, employee_name: str) -> OnboardingRoom:
        """
        Create a new Band room for an employee onboarding session.
        All 4 agents are recruited into this room.
        """
        room_name = f"onboarding-{employee_name.lower().replace(' ', '-')}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        room_id = await self.planner_client.create_room(room_name)

        room = OnboardingRoom(room_id=room_id, employee_name=employee_name)
        self.rooms[room_id] = room

        logger.success(f"Created Band room: {room_id} for {employee_name}")
        return room

    def get_room(self, room_id: str) -> Optional[OnboardingRoom]:
        return self.rooms.get(room_id)

    def get_all_rooms(self) -> List[dict]:
        return [room.to_dict() for room in self.rooms.values()]
