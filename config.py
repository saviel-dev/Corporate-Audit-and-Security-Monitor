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
    # DATABASE_URL es obligatoria. Si no existe en el entorno, la app falla al
    # arrancar — no existe fallback para evitar exponer credenciales en el codigo.
    SQLALCHEMY_DATABASE_URI: str = os.environ["DATABASE_URL"]
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ── Configuración del Scraper (T-13) ──
    # Uso de playwright-stealth para evadir protección antibot (ej. Cloudflare en CO)
    USE_STEALTH_MODE = os.getenv("USE_STEALTH_MODE", "True").lower() in ["true", "1", "yes"]
    # Pausa estática en segundos entre extracciones de un mismo estado para evitar rate limiting
    SCRAPER_DELAY_SECONDS = int(os.getenv("SCRAPER_DELAY_SECONDS", "4"))
    # Porcentaje mínimo aceptable (0.0 a 1.0) de extracciones exitosas por estado
    UMBRAL_TASA_EXITO = float(os.getenv("UMBRAL_TASA_EXITO", "0.80"))

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
    SCRAPER_TIMEOUT = 30_000  # ms
    SCRAPER_RETRIES = 3
    SCRAPER_DELAY = 2  # seconds between retries

    # ── Filtros de Estados de Entidad ─────────────────────────────────────────
    ESTADOS_ENTIDAD_EXCLUIDOS = [
        "Judicially Dissolved",
        "Voluntarily Dissolved",
        "Administratively Dissolved",
        "Dissolved (Term Expired)",
        "Withdrawn",
        "Revoked",
        "Merged",
        "Converted",
        "Consolidated"
    ]
    ESTADOS_ENTIDAD_ALERTA = ["Registered Agent Resigned"]

    # ── WAF Protection ────────────────────────────────────────────────────────
    MAX_WAF_BLOCKS = 2
    WAF_COOLDOWN_MINUTOS = int(os.environ.get("WAF_COOLDOWN_MINUTOS", 120))
    PATRONES_BLOQUEO_WAF = [
        "you have been blocked",
        "attention required",
        "sorry, you have been blocked"
    ]

    # ── States in scope (MVP: HI+CO / Phase 2: all 9) ─────────────────────────
    SUPPORTED_STATES = ["HI", "CO", "NM", "MS", "NY", "FL", "CA", "DE", "WY"]
    SCRAPER_READY_STATES = ["HI", "CO"]  # States with implemented scrapers

    # ── Prioridad de escaneo (T-02) ───────────────────────────────────────────
    # Orden dentro del ciclo diario: indice 0 = primera en procesarse.
    # Los estados ausentes de esta lista se procesan al final, en orden alfabetico.
    # Para cambiar el orden basta editar esta lista; ningun otro archivo debe tocarse.
    ESTADOS_PRIORITARIOS: list[str] = ["CO", "HI", "NM"]

    # ── Elegibilidad de escaneo (T-03) ────────────────────────────────────────
    # Solo las corporaciones con este valor exacto de `status` entran en la cola.
    # Valor en ingles porque espeja el campo de status del inventario del cliente.
    ESTADO_ELEGIBLE: str = "Available"

    # ── Detection rule ────────────────────────────────────────────────────────
    # Flag as "Potential Theft" if officer name does NOT contain BOTH:
    #   DETECTION_REQUIRED  (must be present)
    #   At least one of DETECTION_ALTERNATES
    DETECTION_REQUIRED = os.environ.get("DETECTION_REQUIRED", "Marcio")
    DETECTION_ALTERNATES = os.environ.get(
        "DETECTION_ALTERNATES", "Garcia,Andrade"
    ).split(",")

    # ── Agentes de servicio corporativo ───────────────────────────────────────
    # Lista de nombres de entidades que actuan como servicios de agente registrado.
    # Necesario para distinguir entre "entidad pura" y "entidad propia del dueno".
    AGENTES_SERVICIO_CONOCIDOS = [
        "CT CORPORATION SYSTEM",
        "REGISTERED AGENTS INC",
        "COGENCY GLOBAL",
        "NORTHWEST REGISTERED AGENT",
        "CORPORATION SERVICE COMPANY",
        "LEGALZOOM",
        "INCFILE",
        "HARBOR COMPLIANCE",
        "UNITED STATES CORPORATION AGENTS",
    ]

    # ── Scheduler ─────────────────────────────────────────────────────────────
    DAILY_RUN_HOUR = int(os.environ.get("DAILY_RUN_HOUR", 7))
    DAILY_RUN_MINUTE = int(os.environ.get("DAILY_RUN_MINUTE", 0))
    SCHEDULER_ENABLED = os.environ.get("SCHEDULER_ENABLED", "False").lower() == "true"

    # ── Cloud Storage ─────────────────────────────────────────────────────────
    CLOUD_PROVIDER = os.environ.get(
        "CLOUD_PROVIDER", "none"
    )  # "dropbox" | "gdrive" | "none"
    DROPBOX_ACCESS_TOKEN = os.environ.get("DROPBOX_ACCESS_TOKEN", "")
    GDRIVE_CREDENTIALS = os.environ.get("GDRIVE_CREDENTIALS_FILE", "")
    GDRIVE_FOLDER_ID = os.environ.get("GDRIVE_FOLDER_ID", "")
    CLOUD_BASE_PATH = os.environ.get("CLOUD_BASE_PATH", "/Corporate Monitor")

    # ── Email ─────────────────────────────────────────────────────────────────
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_RECIPIENTS = [
        r.strip() for r in os.environ.get("MAIL_RECIPIENTS", "").split(",") if r.strip()
    ]
    MAIL_FROM = os.environ.get("MAIL_FROM", os.environ.get("MAIL_USERNAME", ""))

    @staticmethod
    def ensure_directories() -> None:
        """Crea los directorios necesarios si no existen."""
        for folder in [
            Config.UPLOAD_FOLDER,
            Config.OUTPUT_FOLDER,
            os.path.join(Config.OUTPUT_FOLDER, "pdfs"),
            os.path.join(Config.OUTPUT_FOLDER, "reports"),
        ]:
            os.makedirs(folder, exist_ok=True)

    @staticmethod
    def validar_configuracion() -> None:
        """Valida invariantes de configuracion al arranque.

        Lanza ValueError si ESTADOS_PRIORITARIOS contiene codigos que no
        estan en SUPPORTED_STATES, evitando configuraciones inconsistentes
        que producirian resultados silenciosamente erroneos.
        """
        extras = set(Config.ESTADOS_PRIORITARIOS) - set(Config.SUPPORTED_STATES)
        if extras:
            raise ValueError(
                f"ESTADOS_PRIORITARIOS contiene estados no incluidos en "
                f"SUPPORTED_STATES: {sorted(extras)}. "
                f"Agrega esos estados a SUPPORTED_STATES o eliminalos de "
                f"ESTADOS_PRIORITARIOS."
            )

        extras_scraper = set(Config.ESTADOS_PRIORITARIOS) - set(
            Config.SCRAPER_READY_STATES
        )
        if extras_scraper:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                "ADVERTENCIA DE ARRANQUE: ESTADOS_PRIORITARIOS incluye estados "
                "sin scraper implementado en SCRAPER_READY_STATES: %s. "
                "Estos estados seran ignorados silenciosamente en la cola.",
                sorted(extras_scraper),
            )
