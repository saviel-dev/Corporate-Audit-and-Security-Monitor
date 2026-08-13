"""
scripts/migrar_status_a_ingles.py

Migra los valores del campo `status` de Corporation de español a inglés,
alineando con el valor canónico del inventario del cliente.

Mapa de traducción:
  "Disponible" -> "Available"
  "Vendida"    -> "Sold"

Idempotente: ejecutar dos veces no tiene efecto la segunda.
Transaccional: si ocurre cualquier error, rollback completo.

Uso:
    python scripts/migrar_status_a_ingles.py
"""

import os
import sys

# Permite importar el paquete app desde la raiz del proyecto
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import func  # noqa: E402

from app import create_app, db  # noqa: E402
from app.models import Corporation  # noqa: E402

# Mapa de traduccion: valor antiguo -> valor nuevo
MAPA_TRADUCCION = {
    "Disponible": "Available",
    "Vendida": "Sold",
}


def ejecutar_migracion() -> None:
    """Aplica el mapa de traduccion en una transaccion atomica."""
    app = create_app()
    with app.app_context():
        # Conteo ANTES
        print("=== Estado ANTES de la migracion ===")
        conteo_antes = (
            db.session.query(Corporation.status, func.count())
            .group_by(Corporation.status)
            .all()
        )
        total_antes = sum(c for _, c in conteo_antes)
        for estado, conteo in conteo_antes:
            print(f"  [{repr(estado)}] -> {conteo}")
        print(f"  TOTAL: {total_antes}")

        # Verificacion de idempotencia: si ya no quedan valores en espanol, no hay nada que hacer
        valores_actuales = {e for e, _ in conteo_antes}
        valores_a_migrar = set(MAPA_TRADUCCION.keys()) & valores_actuales
        if not valores_a_migrar:
            print("\nMigracion ya aplicada previamente. Nada que hacer.")
            _verificar_cola()
            return

        # Migracion dentro de transaccion
        try:
            total_actualizados = 0
            for valor_viejo, valor_nuevo in MAPA_TRADUCCION.items():
                corps = Corporation.query.filter_by(status=valor_viejo).all()
                for corp in corps:
                    corp.status = valor_nuevo
                    total_actualizados += 1
                if corps:
                    print(
                        f"\n  Migradas {len(corps)} corps: '{valor_viejo}' -> '{valor_nuevo}'"
                    )

            db.session.commit()
            print(f"\n  Commit exitoso. {total_actualizados} registros actualizados.")
        except Exception as exc:
            db.session.rollback()
            print(f"\n  ERROR durante la migracion: {exc}")
            print("  Rollback completado. Ninguna fila fue modificada.")
            sys.exit(1)

        # Conteo DESPUES
        print("\n=== Estado DESPUES de la migracion ===")
        conteo_despues = (
            db.session.query(Corporation.status, func.count())
            .group_by(Corporation.status)
            .all()
        )
        total_despues = sum(c for _, c in conteo_despues)
        for estado, conteo in conteo_despues:
            print(f"  [{repr(estado)}] -> {conteo}")
        print(f"  TOTAL: {total_despues}")

        if total_antes != total_despues:
            print(
                f"\n  ALERTA: el total cambio de {total_antes} a {total_despues}."
                " Revisa manualmente."
            )
            sys.exit(1)

        _verificar_cola()


def _verificar_cola() -> None:
    """Reporta cuantas corps entran en la cola con el filtro de lista blanca."""
    from app.models import Corporation

    supported = ["HI", "CO", "NM", "MS", "NY", "FL", "CA", "DE", "WY"]
    estado_elegible = "Available"

    cola = Corporation.query.filter(
        Corporation.status == estado_elegible,
        Corporation.state.in_(supported),
    ).all()

    print(f"\n=== Verificacion de cola (estado_elegible='{estado_elegible}') ===")
    print(f"  Corps en cola: {len(cola)}")

    if len(cola) < 30:
        print(
            f"\n  ALERTA: la cola tiene solo {len(cola)} corps."
            " Esperabamos ~34. Detente y revisa."
        )
        sys.exit(1)
    else:
        print("  OK: la cola supera el umbral minimo esperado (30 corps).")


if __name__ == "__main__":
    ejecutar_migracion()
