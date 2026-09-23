import sys

file_path = r'app\routes.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

bad_str = '''from app.models import SystemSettings, ABBR_STATE, STATE_ABBR, Corporation, DailyRun,
                        ScanResult, StateConfig)'''
good_str = '''from app.models import (SystemSettings, ABBR_STATE, STATE_ABBR, Corporation, DailyRun,
                        ScanResult, StateConfig)'''

content = content.replace(bad_str, good_str)
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
