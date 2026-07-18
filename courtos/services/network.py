from typing import List
from courtos.models import NetworkAllocation, Incident
from courtos.models.enums import Severity, IncidentStatus

class NetworkPolicyService:
    """Service class.
    """

    def calculate_allocation(self, active_incidents: List[Incident]) -> NetworkAllocation:
        has_critical = any(
            i.severity == Severity.CRITICAL and i.status == IncidentStatus.ACTIVE
            for i in active_incidents
        )

        if has_critical:
            return NetworkAllocation(
                broadcast=20.0,
                telemetry=20.0,
                operations=10.0,
                emergency=50.0,
                simulated=True
            )
        else:
            return NetworkAllocation(
                broadcast=40.0,
                telemetry=30.0,
                operations=20.0,
                emergency=10.0,
                simulated=True
            )
