import sys

file_path = r'app\routes.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('from app.models import SystemSettings, (ABBR_STATE, STATE_ABBR,', 'from app.models import SystemSettings, ABBR_STATE, STATE_ABBR,')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
