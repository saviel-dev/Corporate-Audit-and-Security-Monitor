import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    # ── App ──────────────────────────────────────────────────────────────────
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
    DEBUG = os.environ.get("DEBUG", "True").lower() == "true"

    # ── Database ──────────────────────────────────────────────────────────────
    # Only use Neon DB. Fallback to the provided Neon URL if environment variable is missing.
    _neon_db = "postgresql://neondb_owner:npg_2ZrioOxVb5RX@ep-broad-block-avz1v0wq-pooler.c-11.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", _neon_db)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Enable connection pooling health checks (vital for Neon/Serverless Postgres)
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

    # ── File paths ────────────────────────────────────────────────────────────
    if os.environ.get("VERCEL"):
        UPLOAD_FOLDER = "/tmp/uploads"
        OUTPUT_FOLDER = "/tmp/output"
    else:
        UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
        OUTPUT_FOLDER = os.path.join(BASE_DIR, "output")
        
    ALLOWED_EXTENSIONS = {"csv", "txt", "tsv"}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB

    # ── Scraping ──────────────────────────────────────────────────────────────
    SCRAPER_TIMEOUT = 30_000          # ms
    SCRAPER_RETRIES = 3
    SCRAPER_DELAY = 2                 # seconds between retries

    # ── States in scope (MVP: HI+CO / Phase 2: all 9) ─────────────────────────
    SUPPORTED_STATES = ["HI", "CO", "NM", "MS", "NY", "FL", "CA", "DE", "WY"]
    SCRAPER_READY_STATES = ["HI", "CO"]   # States with implemented scrapers

    # ── Detection rule ────────────────────────────────────────────────────────
    # Flag as "Potential Theft" if officer name does NOT contain BOTH:
    #   DETECTION_REQUIRED  (must be present)
    #   At least one of DETECTION_ALTERNATES
    DETECTION_REQUIRED   = os.environ.get("DETECTION_REQUIRED", "Marcio")
    DETECTION_ALTERNATES = os.environ.get(
        "DETECTION_ALTERNATES", "Garcia,Andrade"
    ).split(",")

    # ── Scheduler ─────────────────────────────────────────────────────────────
    DAILY_RUN_HOUR   = int(os.environ.get("DAILY_RUN_HOUR", 7))
    DAILY_RUN_MINUTE = int(os.environ.get("DAILY_RUN_MINUTE", 0))
    SCHEDULER_ENABLED = os.environ.get("SCHEDULER_ENABLED", "False").lower() == "true"

    # ── Cloud Storage ─────────────────────────────────────────────────────────
    CLOUD_PROVIDER        = os.environ.get("CLOUD_PROVIDER", "none")   # "dropbox" | "gdrive" | "none"
    DROPBOX_ACCESS_TOKEN  = os.environ.get("DROPBOX_ACCESS_TOKEN", "")
    GDRIVE_CREDENTIALS    = os.environ.get("GDRIVE_CREDENTIALS_FILE", "")
    GDRIVE_FOLDER_ID      = os.environ.get("GDRIVE_FOLDER_ID", "")
    CLOUD_BASE_PATH       = os.environ.get("CLOUD_BASE_PATH", "/Corporate Monitor")

    # ── Email ─────────────────────────────────────────────────────────────────
    MAIL_SERVER     = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT       = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS    = True
    MAIL_USERNAME   = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD   = os.environ.get("MAIL_PASSWORD", "")
    MAIL_RECIPIENTS = [r.strip() for r in os.environ.get("MAIL_RECIPIENTS", "").split(",") if r.strip()]
    MAIL_FROM       = os.environ.get("MAIL_FROM", os.environ.get("MAIL_USERNAME", ""))

    @staticmethod
    def ensure_directories():
        """Create required directories if they don't exist."""
        for folder in [
            Config.UPLOAD_FOLDER,
            Config.OUTPUT_FOLDER,
            os.path.join(Config.OUTPUT_FOLDER, "pdfs"),
            os.path.join(Config.OUTPUT_FOLDER, "reports"),
        ]:
            os.makedirs(folder, exist_ok=True)
