import os

ADMIN_TELEGRAM_ID = int(os.environ.get("ADMIN_TELEGRAM_ID", "0"))
NOTIFICATION_REDIRECT_MODE = os.environ.get("NOTIFICATION_REDIRECT_MODE", "off")
REPORT_NOTIFY_GERENTE = os.environ.get("REPORT_NOTIFY_GERENTE", "false").lower() == "true"
