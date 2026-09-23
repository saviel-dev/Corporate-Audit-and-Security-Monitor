file_path = r'app\routes.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

old_handler = '''    if request.method == "POST":
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
        return redirect(url_for("main.ajustes"))'''

new_handler = '''    if request.method == "POST":
        new_username = request.form.get("admin_username", "").strip()
        new_password = request.form.get("new_password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()
        new_email = request.form.get("notification_emails", "").strip()
        
        # Validate password match
        if new_password and new_password != confirm_password:
            flash("Las contrasenas no coinciden. Por favor verifica.", "error")
            return render_template("ajustes.html", settings=settings)
        
        if new_username:
            settings.admin_username = new_username
            # Update session username
            session["username"] = new_username
        if new_password:
            settings.admin_password_hash = generate_password_hash(new_password)
        settings.notification_emails = new_email
            
        db.session.commit()
        flash("Configuraciones guardadas correctamente.", "success")
        return redirect(url_for("main.ajustes"))'''

if old_handler in content:
    content = content.replace(old_handler, new_handler)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Routes ajustes handler updated OK")
else:
    print("WARN: handler not found exactly")
