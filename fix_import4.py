import sys

file_path = r'app\routes.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

bad_str = '''    from werkzeug.security import check_password_hash, generate_password_hash
from flask import Response, send_file'''
good_str = '''    from flask import Response, send_file'''

content = content.replace(bad_str, good_str)
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
