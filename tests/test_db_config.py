import os
import glob
import re

def test_scripts_no_leen_database_url_directamente():
    scripts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'scripts')
    script_files = glob.glob(os.path.join(scripts_dir, '*.py'))
    
    patron_prohibido = re.compile(r'os\.environ\.get\([\'"]DATABASE_URL[\'"]\)')
    patron_prohibido2 = re.compile(r'os\.getenv\([\'"]DATABASE_URL[\'"]\)')
    
    fallos = []
    
    for script in script_files:
        # Ignorar archivos renombrados por la nueva regla
        if "PELIGRO_neon_restore_NO_EJECUTAR" in script:
            continue
            
        with open(script, 'r', encoding='utf-8') as f:
            contenido = f.read()
            
            if patron_prohibido.search(contenido) or patron_prohibido2.search(contenido):
                fallos.append(os.path.basename(script))
                
    assert not fallos, f"Los siguientes scripts leen DATABASE_URL directamente: {', '.join(fallos)}. Usa app.db_config.obtener_conexion() en su lugar."

if __name__ == '__main__':
    test_scripts_no_leen_database_url_directamente()
    print('Test OK')
