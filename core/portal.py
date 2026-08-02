from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from core.config import get_settings


@dataclass(frozen=True)
class PortalApp:
    app_id: str
    name: str
    description: str
    url: str
    current: bool = False


def app_registry() -> Sequence[PortalApp]:
    settings = get_settings()
    return (
        PortalApp("portal", "FSI Company Portal", "Common company landing page", settings.portal_url),
        PortalApp(
            "export-shipment",
            "Export Shipment Monitoring",
            "Export logistics, delivery and payment monitoring",
            settings.export_shipment_url,
        ),
        PortalApp(
            "qsms",
            "Quality System Monitoring",
            "Automotive quality masters and genealogy",
            settings.qsms_url,
            current=True,
        ),
        PortalApp("hrms", "HRMS", "People, attendance and HR workflows", settings.hrms_url),
    )
