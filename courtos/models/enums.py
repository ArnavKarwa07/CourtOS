from enum import StrEnum

class EventType(StrEnum):
    KINEMATIC = "kinematic"
    GAME_STATE = "game_state"
    NETWORK = "network"
    REVIEW = "review"

class PlayState(StrEnum):
    PRE_GAME = "pre_game"
    LIVE = "live"
    DEAD_BALL = "dead_ball"
    TIMEOUT = "timeout"
    HALFTIME = "halftime"
    POST_GAME = "post_game"

class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

class IncidentStatus(StrEnum):
    ACTIVE = "active"
    RESOLVED = "resolved"
