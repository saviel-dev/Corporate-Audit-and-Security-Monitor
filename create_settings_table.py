import os
from werkzeug.security import generate_password_hash
from app import create_app, db
from app.models import SystemSettings

app = create_app()
with app.app_context():
    db.create_all()
    
    settings = SystemSettings.query.first()
    if not settings:
        default_pwd = app.config.get("ADMIN_PASSWORD", "admin123")
        settings = SystemSettings(
            admin_username="admin",
            admin_password_hash=generate_password_hash(default_pwd),
            notification_emails=str(app.config.get("MAIL_RECIPIENTS", ""))
        )
        db.session.add(settings)
        db.session.commit()
        print("Created default SystemSettings")
    else:
        print("SystemSettings already initialized")
