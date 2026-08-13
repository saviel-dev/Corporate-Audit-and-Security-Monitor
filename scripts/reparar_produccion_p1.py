"""
Reparacion P1: restaura datos corruptos en Neon/Produccion.
Usa transaccion explicita. Verifica conteos de filas afectadas (rowcount).
Si algo no cuadra, hace ROLLBACK automatico.

Uso: python scripts/reparar_produccion_p1.py
"""
import os
import sys

from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL no definida en .env", file=sys.stderr)
    sys.exit(1)

import psycopg2

def ejecutar_reparacion():
    print("Iniciando reparacion en produccion...")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False  # Transaccion explicita
    cur = conn.cursor()

    try:
        # 1. Conteo antes
        cur.execute("SELECT status, COUNT(*) FROM corporations GROUP BY status ORDER BY status;")
        print("\n--- Conteo ANTES ---")
        for row in cur.fetchall():
            print(f"  {row[0]}: {row[1]}")

        # 2. Inventario propio (6 filas)
        cur.execute("""
            UPDATE corporations
            SET status = 'Available'
            WHERE id IN (3, 4, 6, 7, 9, 10)
              AND source_file = 'user_templates_-_Hoja_1.csv';
        """)
        afectadas_inventario = cur.rowcount
        print(f"\n[Paso 2] Filas inventario propio actualizadas: {afectadas_inventario} (Esperado: 6)")
        if afectadas_inventario != 6:
            raise RuntimeError(f"Fallo verificacion Paso 2: {afectadas_inventario} != 6")

        # 3. Flores Herrera (id=36)
        cur.execute("""
            UPDATE corporations
            SET status = 'Available'
            WHERE id = 36 AND source_file = 'co-socrata-api';
        """)
        afectadas_socrata = cur.rowcount
        print(f"[Paso 3] Filas Flores Herrera actualizadas: {afectadas_socrata} (Esperado: 1)")
        if afectadas_socrata != 1:
            raise RuntimeError(f"Fallo verificacion Paso 3: {afectadas_socrata} != 1")

        # 4. Borrar basura (y sus dependencias en scan_results)
        cur.execute("""
            DELETE FROM scan_results 
            WHERE corporation_id IN (SELECT id FROM corporations WHERE source_file = 'test');
        """)
        afectadas_scan_results = cur.rowcount
        print(f"[Paso 4a] scan_results vinculados a la basura eliminados: {afectadas_scan_results} (Esperado: 3)")
        if afectadas_scan_results != 3:
            raise RuntimeError(f"Fallo verificacion Paso 4a: {afectadas_scan_results} != 3")

        cur.execute("DELETE FROM corporations WHERE source_file = 'test';")
        afectadas_basura = cur.rowcount
        print(f"[Paso 4b] Filas basura eliminadas: {afectadas_basura} (Esperado: 8)")
        if afectadas_basura != 8:
            raise RuntimeError(f"Fallo verificacion Paso 4b: {afectadas_basura} != 8")

        # 5. Conteo despues
        cur.execute("SELECT status, COUNT(*) FROM corporations GROUP BY status ORDER BY status;")
        print("\n--- Conteo DESPUES ---")
        total = 0
        for row in cur.fetchall():
            print(f"  {row[0]}: {row[1]}")
            total += row[1]
        print(f"  Total filas: {total}")

        # Comprobacion de seguridad extra (Available=34, Sold=3, Total=37)
        cur.execute("SELECT COUNT(*) FROM corporations WHERE status='Available';")
        count_available = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM corporations WHERE status='Sold';")
        count_sold = cur.fetchone()[0]
        
        if count_available != 34 or count_sold != 3 or total != 37:
            raise RuntimeError(f"Fallo verificacion de totales. Available={count_available}, Sold={count_sold}, Total={total}. Esperado: 34, 3, 37.")

        # Si llegamos aqui, todo cuadra
        print("\nTodos los rowcounts verificados correctamente.")
        print("Para aplicar los cambios, cambia 'if False:' a 'if True:' en el script.")
        
        if True: # GUARDIA FINAL (Aprobado por el usuario)
            conn.commit()
            print("COMMIT REALIZADO CON EXITO.")
        else:
            conn.rollback()
            print("SIMULACION COMPLETADA. ROLLBACK realizado por defecto.")

    except Exception as e:
        conn.rollback()
        print(f"\nERROR: {e}")
        print("ROLLBACK AUTOMATICO realizado. No se han guardado cambios.")
        sys.exit(1)
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    ejecutar_reparacion()
