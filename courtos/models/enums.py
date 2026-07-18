from enum import StrEnum

class EventType(StrEnum):
    """Class description.\n"""

    KINEMATIC = "kinematic"
    GAME_STATE = "game_state"
    NETWORK = "network"
    REVIEW = "review"

class PlayState(StrEnum):
    """Class description.\n"""

    PRE_GAME = "pre_game"
    LIVE = "live"
    DEAD_BALL = "dead_ball"
    TIMEOUT = "timeout"
    HALFTIME = "halftime"
    POST_GAME = "post_game"

class Severity(StrEnum):
    """Class description.\n"""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

class IncidentStatus(StrEnum):
    """Class description.\n"""

    ACTIVE = "active"
    RESOLVED = "resolved"
