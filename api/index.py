import sys
import os

# Agregamos la ruta del proyecto al path para que Python encuentre el módulo 'app'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app

# Vercel necesita que la instancia de Flask se llame 'app' por defecto
app = create_app()
