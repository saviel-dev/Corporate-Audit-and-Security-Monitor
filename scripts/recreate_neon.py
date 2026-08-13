import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app import create_app, db

app = create_app()
with app.app_context():
    print("Recreando tablas en Neon...")
    db.create_all()
    print("Tablas creadas.")
