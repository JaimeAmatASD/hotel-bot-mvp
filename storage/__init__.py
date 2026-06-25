"""Storage package — preserves the legacy `storage.*` API.

Tests and callers can patch `storage.DB_PATH` exactly as before; the value
is shared via `storage._conn.DB_PATH` and re-exported here.
"""
from storage._conn import DB_PATH, _conn
from storage.schema import init_db
from storage.display import generate_display_id
from storage.classifications import (
    save,
    get_incident,
    get_incident_assignee,
    update_classification,
    get_incidents_for_room,
    get_guest_intel_for_room,
    get_observations_for_room,
    search_classifications,
)
from storage.events import (
    save_event,
    get_events_for_incident,
    update_incident_state_atomic,
    get_incident_with_events,
)
from storage.notifications import (
    save_notification,
    get_notifications_for_incident,
    get_recent_notifications,
)
from storage.preferences import (
    get_debug_mode,
    set_debug_mode,
    get_notification_preferences,
    set_notification_mode,
    toggle_excluded_department,
)
from storage.reports import (
    create_report,
    get_report_with_items,
    link_classification_to_report,
    link_classifications_to_report,
    get_classifications_for_employee_recent,
)
from storage.queries import (
    get_open_incidents,
    get_incidents_assigned_to,
    get_resolved_incidents,
    get_employees,
    get_employee_stats,
    get_all_history,
)

__all__ = [
    "DB_PATH", "_conn", "init_db", "generate_display_id",
    "save", "get_incident", "get_incident_assignee", "update_classification",
    "get_incidents_for_room", "get_guest_intel_for_room",
    "get_observations_for_room", "search_classifications",
    "save_event", "get_events_for_incident",
    "update_incident_state_atomic", "get_incident_with_events",
    "save_notification", "get_notifications_for_incident", "get_recent_notifications",
    "get_debug_mode", "set_debug_mode",
    "get_notification_preferences", "set_notification_mode", "toggle_excluded_department",
    "create_report", "get_report_with_items",
    "link_classification_to_report", "link_classifications_to_report",
    "get_classifications_for_employee_recent",
    "get_open_incidents", "get_incidents_assigned_to", "get_resolved_incidents",
    "get_employees", "get_employee_stats", "get_all_history",
]
