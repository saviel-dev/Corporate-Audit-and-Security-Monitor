import sys, re

file_path = r'app\routes.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Add imports
if 'from werkzeug.security import' not in content:
    content = content.replace('from flask import ', 'from werkzeug.security import check_password_hash, generate_password_hash\nfrom flask import ')
if 'from app.models import' in content and 'SystemSettings' not in content:
    content = content.replace('from app.models import ', 'from app.models import SystemSettings, ')
elif 'from app.models import' not in content:
    content = content.replace('from flask import ', 'from app.models import SystemSettings\nfrom flask import ')

# Replace login logic
# It checks: if username == "admin" and password == current_app.config.get("ADMIN_PASSWORD", "admin123"):
# We have two places (AJAX and form)
old_login_ajax = '''if username == "admin" and password == current_app.config.get(
                "ADMIN_PASSWORD", "admin123"
            ):'''
new_login_ajax = '''settings = SystemSettings.query.first()
            if settings and username == settings.admin_username and check_password_hash(settings.admin_password_hash, password):'''

old_login_form = '''if username == "admin" and password == current_app.config.get(
            "ADMIN_PASSWORD", "admin123"
        ):'''
new_login_form = '''settings = SystemSettings.query.first()
        if settings and username == settings.admin_username and check_password_hash(settings.admin_password_hash, password):'''

content = content.replace(old_login_ajax, new_login_ajax)
content = content.replace(old_login_form, new_login_form)

# Add ajustes route
ajustes_route = '''
@main_bp.route("/ajustes", methods=["GET", "POST"])
def ajustes():
    if not session.get("logged_in"):
        return redirect(url_for("main.login"))
        
    settings = SystemSettings.query.first()
    if not settings:
        # Fallback if somehow not initialized
        settings = SystemSettings(admin_username="admin", admin_password_hash=generate_password_hash("admin123"))
        db.session.add(settings)
        db.session.commit()
        
    if request.method == "POST":
        new_username = request.form.get("username")
        new_password = request.form.get("password")
        new_email = request.form.get("email")
        
        if new_username:
            settings.admin_username = new_username
        if new_password:
            settings.admin_password_hash = generate_password_hash(new_password)
        if new_email is not None:
            settings.notification_emails = new_email
            
        db.session.commit()
        flash("Configuraciones guardadas correctamente.", "success")
        return redirect(url_for("main.ajustes"))
        
    return render_template("ajustes.html", settings=settings)
'''

if 'def ajustes():' not in content:
    content += ajustes_route

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Routes patched successfully.")
