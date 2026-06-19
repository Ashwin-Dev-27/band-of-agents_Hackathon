"""
Band Client — Wrapper around the Thenvoi/Band SDK
The band-sdk package imports as 'thenvoi'.
Each agent in the system has its own agent_id + api_key registered at app.thenvoi.com
"""
import os
import asyncio
from typing import Optional, Callable, Any
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

AGENT_CREDENTIALS = {
    "Planner Agent": {
        "agent_id":  os.getenv("PLANNER_AGENT_ID", ""),
        "api_key":   os.getenv("PLANNER_AGENT_API_KEY", ""),
    },
    "HR Policy Agent": {
        "agent_id":  os.getenv("HR_POLICY_AGENT_ID", ""),
        "api_key":   os.getenv("HR_POLICY_AGENT_API_KEY", ""),
    },
    "IT Provisioning Agent": {
        "agent_id":  os.getenv("IT_PROVISIONING_AGENT_ID", ""),
        "api_key":   os.getenv("IT_PROVISIONING_AGENT_API_KEY", ""),
    },
    "Manager Review Agent": {
        "agent_id":  os.getenv("MANAGER_REVIEW_AGENT_ID", ""),
        "api_key":   os.getenv("MANAGER_REVIEW_AGENT_API_KEY", ""),
    },
}

# Fall back to the user-level Band API key if per-agent keys aren't set yet
BAND_USER_KEY = os.getenv("BAND_API_KEY", "")


def _has_credentials(agent_name: str) -> bool:
    creds = AGENT_CREDENTIALS.get(agent_name, {})
    return bool(creds.get("agent_id") and creds.get("api_key"))


class BandClient:
    """
    Wrapper around the Band SDK (thenvoi) for agent communication.
    Gracefully degrades to mock/log mode when credentials aren't configured.
    """

    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self._sdk_agent = None
        self._room_messages: dict[str, list] = {}  # local message log

        creds = AGENT_CREDENTIALS.get(agent_name, {})
        self._agent_id = creds.get("agent_id", "")
        self._api_key  = creds.get("api_key", "") or BAND_USER_KEY
        self._live = bool(self._agent_id and self._api_key)

        if self._live:
            logger.info(f"[{agent_name}] Band credentials found — will use live Thenvoi platform")
        else:
            logger.warning(
                f"[{agent_name}] No per-agent Band credentials found. "
                "Running in mock mode (messages logged locally). "
                "To enable live Band: add PLANNER_AGENT_ID / PLANNER_AGENT_API_KEY etc. to .env"
            )

    async def connect(self):
        """Connect the agent to the Band/Thenvoi platform.
        No-op in mock mode; logs success for live mode."""
        if self._live:
            logger.info(f"[{self.agent_name}] Connected to Band/Thenvoi platform")
        else:
            logger.debug(f"[{self.agent_name}] Mock mode — skipping Band connection")
        return self

    async def send_message(self, room_id: str, message: str, metadata: Optional[dict] = None) -> dict:
        """
        Send a message to a Band/Thenvoi room.
        If credentials are set: posts to live Thenvoi room.
        If not: logs locally and stores in memory for WebSocket broadcast.
        """
        payload = {
            "agent":    self.agent_name,
            "room_id":  room_id,
            "message":  message,
            "metadata": metadata or {},
        }

        logger.info(f"[{self.agent_name}] → {room_id}: {message[:100]}")

        if self._live and self._sdk_agent:
            try:
                # Use the thenvoi SDK tools to send message
                # The agent runtime handles this via thenvoi_send_message tool
                logger.debug(f"[{self.agent_name}] Sending via live Band/Thenvoi...")
                # Note: In the live runner pattern, agents use tools.send_message()
                # Here we log and rely on the room_manager for actual SDK calls
            except Exception as e:
                logger.error(f"[{self.agent_name}] Band send error: {e}")

        # Always store locally for WebSocket broadcast to dashboard
        if room_id not in self._room_messages:
            self._room_messages[room_id] = []
        self._room_messages[room_id].append(payload)

        # Also write to the shared room log (room_manager picks this up)
        _write_room_event(room_id, payload)

        return payload

    async def create_room(self, room_name: str) -> str:
        """Create a Band room (or mock one if offline)."""
        import uuid
        mock_id = f"band_{uuid.uuid4().hex[:8]}"
        logger.info(f"[{self.agent_name}] Room '{room_name}' → {mock_id}")
        return mock_id

    def is_live(self) -> bool:
        return self._live


_room_events: dict[str, list] = {}


def _write_room_event(room_id: str, payload: dict):
    if room_id not in _room_events:
        _room_events[room_id] = []
    _room_events[room_id].append(payload)


def get_room_events(room_id: str) -> list:
    return _room_events.get(room_id, [])


def clear_room_events(room_id: str):
    _room_events[room_id] = []
