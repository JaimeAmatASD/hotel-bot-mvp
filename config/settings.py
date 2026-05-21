import os

ADMIN_TELEGRAM_ID = int(os.environ.get("ADMIN_TELEGRAM_ID", "0"))
NOTIFICATION_REDIRECT_MODE = os.environ.get("NOTIFICATION_REDIRECT_MODE", "off")

REPORT_TIMEOUT_HOURS = 12
REPORT_OPEN_KEYWORDS = ["inicio reporte", "inicio de reporte", "abrir reporte"]
REPORT_CLOSE_KEYWORDS = ["cierre de reporte", "cerrar reporte", "fin reporte"]
