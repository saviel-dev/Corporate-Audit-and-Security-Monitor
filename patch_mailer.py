import sys

file_path = r'app\services\mailer.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

old_logic = '''    recipients = cfg.get("MAIL_RECIPIENTS", [])
    if not recipients or recipients == [""]:'''

new_logic = '''    # Fetch from SystemSettings
    from app.models import SystemSettings
    settings = SystemSettings.query.first()
    
    recipients_str = settings.notification_emails if settings and settings.notification_emails else cfg.get("MAIL_RECIPIENTS", "")
    
    if isinstance(recipients_str, list):
        recipients = recipients_str
    else:
        recipients = [r.strip() for r in recipients_str.split(",") if r.strip()]

    if not recipients:'''

if 'from app.models import SystemSettings' not in content:
    content = content.replace(old_logic, new_logic)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched mailer.py")
else:
    print("mailer.py already patched")
