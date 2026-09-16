import os
import sys
from urllib.parse import urlparse
import psycopg2
import sqlite3
from dotenv import load_dotenv

def obtener_conexion(destino, escritura=False):
    if destino not in ["local", "produccion"]:
        raise ValueError("destino debe ser 'local' o 'produccion'")

    if destino == "produccion":
        # Cargar explicitamente las variables de Neon
        load_dotenv('.env.neon', override=True)
        db_url = os.environ.get("DATABASE_URL")
        
        if not db_url or "neon.tech" not in db_url:
            raise RuntimeError("DATABASE_URL de produccion no encontrada o invalida en .env.neon")
            
        conn = psycopg2.connect(db_url)
        conn.autocommit = False
        
        # Conteo de filas
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM corporations;")
        filas = cur.fetchone()[0]
        cur.close()
        
        parsed = urlparse(db_url)
        host = parsed.hostname
        
        print(f"*** PRODUCCION (Neon) | Host: {host} | Filas: {filas} ***")
        
        if escritura:
            print("ADVERTENCIA: Vas a realizar operaciones de ESCRITURA en produccion.")
            confirm = input("Escribe 'CONFIRMO' para continuar: ")
            if confirm.strip() != "CONFIRMO":
                print("Operacion cancelada por el usuario.")
                sys.exit(1)
                
        return conn

    else:
        # local
        load_dotenv('.env', override=True)
        db_url = os.environ.get("DATABASE_URL")
        if not db_url or not db_url.startswith("sqlite:///"):
            raise RuntimeError("DATABASE_URL local debe ser sqlite")
            
        path = db_url.replace("sqlite:///", "")
        conn = sqlite3.connect(path)
        return conn

def obtener_url_conexion(destino):
    if destino not in ['local', 'produccion']:
        raise ValueError("destino debe ser 'local' o 'produccion'")
    if destino == 'produccion':
        load_dotenv('.env.neon', override=True)
    else:
        load_dotenv('.env', override=True)
    return os.environ.get('DATABASE_URL')
