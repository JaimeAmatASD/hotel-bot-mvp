import os

ADMIN_TELEGRAM_ID = int(os.environ.get("ADMIN_TELEGRAM_ID", "0"))
NOTIFICATION_REDIRECT_MODE = os.environ.get("NOTIFICATION_REDIRECT_MODE", "off")
