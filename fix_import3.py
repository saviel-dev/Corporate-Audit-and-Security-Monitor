import sys

file_path = r'app\routes.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

bad_str = '''        from werkzeug.security import check_password_hash, generate_password_hash
from flask import current_app'''
good_str = '''        from flask import current_app'''

content = content.replace(bad_str, good_str)

# Ensure the import is at the top
if 'from werkzeug.security import check_password_hash, generate_password_hash' not in content:
    content = 'from werkzeug.security import check_password_hash, generate_password_hash\n' + content

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
