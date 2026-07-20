import os
import logging

from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from flask_babel import Babel
from flask_socketio import SocketIO
from config import Config

logger = logging.getLogger(__name__)

db = SQLAlchemy()
babel = Babel()
socketio = SocketIO(cors_allowed_origins="*")

def get_locale():
    lang = request.cookies.get('lang')
    if lang in ['es', 'en']:
        return lang
    return 'en'  # Default: English

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    app.config['BABEL_DEFAULT_LOCALE'] = 'en'
    # translations/ is at the project root, one level above app/
    app.config['BABEL_TRANSLATION_DIRECTORIES'] = os.path.join(
        os.path.dirname(app.root_path), 'translations'
    )

    # Ensure required directories exist
    config_class.ensure_directories()

    # Init extensions
    db.init_app(app)
    babel.init_app(app, locale_selector=get_locale)
    socketio.init_app(app, async_mode='threading')

    # Register blueprints
    from app.routes import main_bp
    app.register_blueprint(main_bp)

    # Create / migrate tables
    with app.app_context():
        db.create_all()
        
        # Clean up any interrupted runs (if the server restarted while running)
        from app.models import DailyRun
        interrupted = DailyRun.query.filter_by(status="running").all()
        for r in interrupted:
            r.status = "error"
        if interrupted:
            db.session.commit()

    # Start daily scheduler (only if enabled in config)
    if app.config.get("SCHEDULER_ENABLED", False):
        _start_scheduler(app)

    return app


def _start_scheduler(app) -> None:
    """
    Start APScheduler for the daily automated scan.

    Scheduled time is read from config:
      DAILY_RUN_HOUR   (default 7)
      DAILY_RUN_MINUTE (default 0)

    Set SCHEDULER_ENABLED=True in .env to activate.
    """
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
        from app.services.scanner import run_daily_scan
        from app import db as _db
        from app.models import DailyRun

        hour   = app.config.get("DAILY_RUN_HOUR", 7)
        minute = app.config.get("DAILY_RUN_MINUTE", 0)

        def _scheduled_job():
            """Called by APScheduler every day at the configured time."""
            with app.app_context():
                try:
                    run = DailyRun(triggered_by="scheduler", status="running")
                    _db.session.add(run)
                    _db.session.commit()
                    logger.info("Scheduler: starting DailyRun #%d", run.id)
                    run_daily_scan(run.id, app)
                except Exception as exc:
                    logger.error("Scheduled scan failed: %s", exc)

        scheduler = BackgroundScheduler(timezone="America/New_York")
        scheduler.add_job(
            _scheduled_job,
            trigger=CronTrigger(hour=hour, minute=minute),
            id="daily_scan",
            replace_existing=True,
        )
        scheduler.start()
        logger.info("APScheduler started — daily scan at %02d:%02d ET", hour, minute)

    except ImportError:
        logger.warning("APScheduler not installed. Install it with: pip install apscheduler")
    except Exception as exc:
        logger.error("Scheduler init failed: %s", exc)
