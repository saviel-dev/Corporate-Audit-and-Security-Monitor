"""
SQLAlchemy models for Corporate Cash Credit Monitor.

Tables:
  - StateConfig   : portal URL per US state (scraper lookup)
  - Corporation   : master list of companies to monitor
  - DailyRun      : one record per automated daily execution
  - ScanResult    : per-corporation result within a DailyRun
"""

from datetime import datetime, timezone

from app import db

# Full state name → 2-letter abbreviation
STATE_ABBR = {
    "Alabama": "AL",
    "Alaska": "AK",
    "Arizona": "AZ",
    "Arkansas": "AR",
    "California": "CA",
    "Colorado": "CO",
    "Connecticut": "CT",
    "Delaware": "DE",
    "Florida": "FL",
    "Georgia": "GA",
    "Hawaii": "HI",
    "Idaho": "ID",
    "Illinois": "IL",
    "Indiana": "IN",
    "Iowa": "IA",
    "Kansas": "KS",
    "Kentucky": "KY",
    "Louisiana": "LA",
    "Maine": "ME",
    "Maryland": "MD",
    "Massachusetts": "MA",
    "Michigan": "MI",
    "Minnesota": "MN",
    "Mississippi": "MS",
    "Missouri": "MO",
    "Montana": "MT",
    "Nebraska": "NE",
    "Nevada": "NV",
    "New Hampshire": "NH",
    "New Jersey": "NJ",
    "New Mexico": "NM",
    "New York": "NY",
    "North Carolina": "NC",
    "North Dakota": "ND",
    "Ohio": "OH",
    "Oklahoma": "OK",
    "Oregon": "OR",
    "Pennsylvania": "PA",
    "Rhode Island": "RI",
    "South Carolina": "SC",
    "South Dakota": "SD",
    "Tennessee": "TN",
    "Texas": "TX",
    "Utah": "UT",
    "Vermont": "VT",
    "Virginia": "VA",
    "Washington": "WA",
    "West Virginia": "WV",
    "Wisconsin": "WI",
    "Wyoming": "WY",
    "District of Columbia": "DC",
    "Puerto Rico": "PR",
}
# Reverse: abbreviation → full name
ABBR_STATE = {v: k for k, v in STATE_ABBR.items()}


class StateConfig(db.Model):
    """Portal URL configuration per US state, used by the scraper."""

    __tablename__ = "state_configs"

    id = db.Column(db.Integer, primary_key=True)
    state_name = db.Column(db.String(64), nullable=False, unique=True, index=True)
    state_code = db.Column(db.String(2), nullable=False, unique=True, index=True)
    search_url = db.Column(db.String(512), nullable=False)
    active = db.Column(db.Boolean, default=True)
    scraper_supported = db.Column(
        db.Boolean, default=False
    )  # True once scraper is built

    # Auto-discovery: True if portal supports searching by officer/agent name
    # False = CSV-only (must receive corp names externally)
    is_officer_searchable = db.Column(db.Boolean, default=False)
    # Comma-separated search terms used for auto-discovery
    # e.g. "Marcio Garcia,Garcia,Andrade"
    discovery_terms = db.Column(db.String(512), nullable=True)
    
    # WAF Protection
    waf_blocked_until = db.Column(db.DateTime, nullable=True)

    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    @classmethod
    def get_url(cls, state_code: str) -> str | None:
        """Return portal URL for a given 2-letter state code."""
        row = cls.query.filter_by(state_code=state_code.upper(), active=True).first()
        return row.search_url if row else None

    @classmethod
    def get_discoverable_states(cls) -> list:
        """Return states that support auto-discovery by officer/agent name."""
        return cls.query.filter_by(
            active=True, scraper_supported=True, is_officer_searchable=True
        ).all()

    @classmethod
    def get_csv_only_states(cls) -> list:
        """Return states that require CSV input (no officer-name search)."""
        return cls.query.filter_by(
            active=True, scraper_supported=True, is_officer_searchable=False
        ).all()

    def __repr__(self):
        return f"<StateConfig {self.state_code}: {self.search_url[:40]}>"


class Corporation(db.Model):
    """A corporate entity imported from CSV (or Salesforce in the future)."""

    __tablename__ = "corporations"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(256), nullable=False, index=True)
    state = db.Column(db.String(2), nullable=False, index=True)  # "HI" | "CO"
    corp_id = db.Column(db.String(128), unique=True, nullable=True)  # State registry ID
    status = db.Column(db.String(64), nullable=False, default="Available")
    priority = db.Column(db.Integer, default=0)  # Higher = first
    date_registered = db.Column(db.Date, nullable=True)  # For age-based sorting
    source_file = db.Column(db.String(256), nullable=True)  # Origin CSV filename

    # Estado en el registro gubernamental (ej. Good Standing, Dissolved)
    estado_entidad_registro = db.Column(db.String(128), nullable=True)
    fecha_ultima_verificacion_estado = db.Column(db.DateTime, nullable=True)

    # Detection criteria: the two required strings the officer name must contain
    required_term_1 = db.Column(db.String(128), nullable=True)
    required_term_2 = db.Column(db.String(128), nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    scan_results = db.relationship(
        "ScanResult", back_populates="corporation", cascade="all, delete-orphan"
    )

    def is_processable(
        self,
        estado_elegible: str = "Available",
        supported_states: list | None = None,
    ) -> bool:
        """Devuelve True si esta corporacion debe entrar en la cola de escaneo.

        Usa lista blanca (estado_elegible) en vez de lista negra para evitar
        que valores inesperados del campo status escapen el filtro.

        Args:
            estado_elegible: valor exacto de status que habilita el escaneo.
                Por defecto 'Available'; sobreescribible desde config.
            supported_states: lista de codigos de estado con scraper activo.
                Si es None, usa los 9 estados del alcance del proyecto.
        """
        if supported_states is None:
            supported_states = ["HI", "CO", "NM", "MS", "NY", "FL", "CA", "DE", "WY"]
        return self.status.strip() == estado_elegible and self.state in supported_states

    def __repr__(self):
        return f"<Corporation {self.name} [{self.state}]>"


class DailyRun(db.Model):
    """Tracks one full daily execution of the monitor."""

    __tablename__ = "daily_runs"

    id = db.Column(db.Integer, primary_key=True)
    started_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    finished_at = db.Column(db.DateTime, nullable=True)
    triggered_by = db.Column(
        db.String(64), default="scheduler"
    )  # "scheduler" | "manual"

    total_processed = db.Column(db.Integer, default=0)
    total_alerts = db.Column(db.Integer, default=0)
    total_warnings = db.Column(db.Integer, default=0)
    total_errors = db.Column(db.Integer, default=0)

    # JSON con el desglose de entidades excluidas por estado muerto
    excluded_status_breakdown = db.Column(db.Text, nullable=True)

    report_csv_path = db.Column(db.String(512), nullable=True)
    report_excel_path = db.Column(db.String(512), nullable=True)
    report_cloud_link = db.Column(
        db.String(1024), nullable=True
    )  # Shared link after upload

    status = db.Column(
        db.String(32), default="running"
    )  # "running" | "done" | "failed"

    scan_results = db.relationship(
        "ScanResult", back_populates="daily_run", cascade="all, delete-orphan"
    )
    
    state_metrics = db.relationship(
        "StateMetrics", back_populates="daily_run", cascade="all, delete-orphan"
    )

    @property
    def duration_seconds(self):
        if self.finished_at and self.started_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None

    def __repr__(self):
        return f"<DailyRun #{self.id} {self.started_at.date() if self.started_at else '?'}>"


class StateMetrics(db.Model):
    """Métricas de éxito por estado para una ejecución diaria."""

    __tablename__ = "state_metrics"

    id = db.Column(db.Integer, primary_key=True)
    daily_run_id = db.Column(db.Integer, db.ForeignKey("daily_runs.id"), nullable=False)
    estado = db.Column(db.String(2), nullable=False, index=True)

    total_intentadas = db.Column(db.Integer, default=0)
    total_extraidas = db.Column(db.Integer, default=0)
    total_no_verificables = db.Column(db.Integer, default=0)
    total_alertas = db.Column(db.Integer, default=0)
    total_bloqueos_waf = db.Column(db.Integer, default=0)

    daily_run = db.relationship("DailyRun", back_populates="state_metrics")

    @property
    def tasa_exito(self) -> float:
        """Porcentaje de corporaciones con agente extraído exitosamente."""
        if self.total_intentadas == 0:
            return 0.0
        return self.total_extraidas / self.total_intentadas

    def __repr__(self):
        return f"<StateMetrics {self.estado} (Run #{self.daily_run_id}): {self.tasa_exito*100:.1f}%>"


class ScanResult(db.Model):
    """Per-corporation result within a DailyRun."""

    __tablename__ = "scan_results"

    id = db.Column(db.Integer, primary_key=True)
    daily_run_id = db.Column(db.Integer, db.ForeignKey("daily_runs.id"), nullable=False)
    corporation_id = db.Column(
        db.Integer, db.ForeignKey("corporations.id"), nullable=False
    )

    scanned_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Raw data from portal
    officer_name_raw = db.Column(db.String(256), nullable=True)
    registered_agent_raw = db.Column(db.String(256), nullable=True)
    portal_status = db.Column(
        db.String(128), nullable=True
    )  # Status text on state website

    # Detection outcome
    alert = db.Column(db.Boolean, default=False)
    is_vulnerable = db.Column(db.Boolean, default=False)
    alert_reason = db.Column(db.String(512), nullable=True)
    status_changed = db.Column(db.Boolean, default=False)  # Changed vs. previous run

    # Evidence
    pdf_path = db.Column(db.String(512), nullable=True)
    cloud_link = db.Column(db.String(1024), nullable=True)

    # Error tracking
    error = db.Column(db.Boolean, default=False)
    error_message = db.Column(db.Text, nullable=True)

    notes = db.Column(db.Text, nullable=True)

    daily_run = db.relationship("DailyRun", back_populates="scan_results")
    corporation = db.relationship("Corporation", back_populates="scan_results")

    def __repr__(self):
        flag = "ALERT" if self.alert else "OK"
        return (
            f"<ScanResult [{flag}] corp={self.corporation_id} run={self.daily_run_id}>"
        )
