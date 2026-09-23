import sys, os

file_path = r'app\models.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

if "class SystemSettings" not in content:
    new_model = '''

class SystemSettings(db.Model):
    __tablename__ = "system_settings"

    id = db.Column(db.Integer, primary_key=True)
    admin_username = db.Column(db.String(64), default="admin", nullable=False)
    admin_password_hash = db.Column(db.String(256), nullable=False)
    notification_emails = db.Column(db.String(512), nullable=True)

    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
'''
    content += new_model
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Added SystemSettings to models.py")
else:
    print("SystemSettings already exists in models.py")
