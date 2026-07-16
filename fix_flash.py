import re

def fix():
    with open("app/routes.py", "r", encoding="utf8") as f:
        c = f.read()
    
    # Simple strings
    c = re.sub(r'flash\(\s*"(.*?)"\s*,\s*"(.*?)"\s*\)', r'flash(_("\1"), "\2")', c)
    # f-strings with {e}
    c = re.sub(r'flash\(\s*f"Error al procesar el archivo: \{e\}"\s*,\s*"error"\s*\)', r'flash(_("Error al procesar el archivo: %(e)s", e=e), "error")', c)
    c = re.sub(r'flash\(\s*f"Error procesando archivo: \{e\}"\s*,\s*"error"\s*\)', r'flash(_("Error procesando archivo: %(e)s", e=e), "error")', c)
    c = re.sub(r'flash\(\s*f"Formato de fecha invÃ¡lido: \{e\}"\s*,\s*"error"\s*\)', r'flash(_("Formato de fecha inválido: %(e)s", e=e), "error")', c)
    c = re.sub(r'flash\(\s*f"Formato de fecha inválido: \{e\}"\s*,\s*"error"\s*\)', r'flash(_("Formato de fecha inválido: %(e)s", e=e), "error")', c)
    
    # f"{sc.state_name} {status}."
    c = re.sub(r'flash\(\s*f"\{sc\.state_name\} \{status\}\."\s*,\s*"success"\s*\)', r'flash(_("%(state)s %(status)s.", state=sc.state_name, status=status), "success")', c)
    
    with open("app/routes.py", "w", encoding="utf8") as f:
        f.write(c)

if __name__ == "__main__":
    fix()
