"""
Servicio para importar inventario desde archivo Excel.
Fase A: Hojas COLORADO, HAWAII, NEW YORK, FLORIDA.
COLORADO QUEUE se excluye temporalmente (D-18).
"""
import io
import pandas as pd
from datetime import datetime, timezone
from typing import Dict, Any
from app import db
from app.models import Corporation

HOJAS_VALIDAS = {
    "COLORADO": "CO",
    "HAWAII": "HI",
    "NEW YORK": "NY",
    "FLORIDA": "FL"
}
HOJA_QUEUE = "COLORADO QUEUE"

def normalizar_nombre(nombre: str) -> str:
    if not nombre or pd.isna(nombre):
        return ""
    # Strip, uppercase y colapsar espacios multiples
    return " ".join(str(nombre).strip().upper().split())

def importar_excel(file_stream: io.BytesIO, filename: str, modo_prueba: bool = True) -> Dict[str, Any]:
    """
    Importa las corporaciones del inventario Excel.
    
    Args:
        file_stream: Stream de bytes del archivo Excel
        filename: Nombre original del archivo (para source_file)
        modo_prueba: Si es True, no hace commit a la base de datos
        
    Returns:
        Diccionario con estadisticas de la importacion.
    """
    stats = {
        "insertadas": 0,
        "actualizadas": 0,
        "sin_cambios": 0,
        "errores": 0,
        "detalles_errores": [],
        "rechazadas_queue": 0,
        "filas_totales_procesadas": 0
    }
    
    try:
        xl = pd.ExcelFile(file_stream)
    except Exception as e:
        stats["errores"] += 1
        stats["detalles_errores"].append(f"Error al leer archivo: {str(e)}")
        return stats

    # Pre-cargar corporaciones existentes para evitar N consultas
    existentes = Corporation.query.all()
    dict_existentes = {(c.name, c.state): c for c in existentes}
    
    # Para insercion por lotes
    BATCH_SIZE = 500
    operaciones_pendientes = 0
    
    # Iterar solo por las hojas validas encontradas en el archivo
    for nombre_hoja in xl.sheet_names:
        if nombre_hoja == HOJA_QUEUE:
            # D-18: Omitir COLORADO QUEUE
            stats["rechazadas_queue"] += 1
            continue
            
        if nombre_hoja not in HOJAS_VALIDAS:
            continue
            
        codigo_estado = HOJAS_VALIDAS[nombre_hoja]
        
        try:
            # header=1 indica que la primera fila (0) es titulo, los encabezados reales estan en la fila 1
            df = pd.read_excel(xl, sheet_name=nombre_hoja, header=1, dtype=str)
        except Exception as e:
            stats["errores"] += 1
            stats["detalles_errores"].append(f"Error al leer hoja {nombre_hoja}: {str(e)}")
            continue

        # Columnas a buscar dependiendo del estado
        col_status = "Status.1" if nombre_hoja == "NEW YORK" else "Status"
        col_age = "Age" if nombre_hoja == "NEW YORK" else "Age "
        
        for idx, row in df.iterrows():
            nombre_crudo = row.get("Corp Name")
            if pd.isna(nombre_crudo) or not str(nombre_crudo).strip():
                continue
                
            nombre_norm = normalizar_nombre(nombre_crudo)
            if not nombre_norm:
                continue
                
            stats["filas_totales_procesadas"] += 1
            
            # Status
            status_val = str(row.get(col_status, "")).strip() if pd.notna(row.get(col_status)) else "Available"
            
            # Auditoria (STOLEN CORP?)
            stolen_val = str(row.get("STOLEN CORP?", "")).strip() if pd.notna(row.get("STOLEN CORP?")) else ""
            auditado_robado = None
            if stolen_val.lower() == "yes":
                auditado_robado = True
            elif stolen_val.lower() == "no":
                auditado_robado = False
                
            # Resto de campos
            proof_val = str(row.get("Proof", "")).strip() if pd.notna(row.get("Proof")) else ""
            url_prueba = proof_val if proof_val and proof_val != "-" else None
            
            note_val = str(row.get("Note", "")).strip() if pd.notna(row.get("Note")) else ""
            nota = note_val if note_val and note_val != "-" else None
            
            age_raw = str(row.get(col_age, "")).strip() if pd.notna(row.get(col_age)) else None
            
            # Client Price (solo HI, FL)
            precio_cliente = None
            price_val = str(row.get("Client Price", "")).strip() if pd.notna(row.get("Client Price")) else ""
            if price_val:
                try:
                    # Remover $ y comas
                    clean_price = price_val.replace("$", "").replace(",", "")
                    precio_cliente = float(clean_price)
                except ValueError:
                    pass
            
            try:
                # Buscar existente en memoria en lugar de BD
                corp = dict_existentes.get((nombre_norm, codigo_estado))
                
                if corp:
                    tiene_cambios = False
                    campos_cambiados = []
                    
                    # Logica auditado_robado
                    nuevo_auditado = corp.auditado_robado
                    # D-17: auditado_robado True no se puede sobreescribir con False o None automaticamente
                    if corp.auditado_robado is True and auditado_robado is not True:
                        pass # Mantiene el True
                    else:
                        nuevo_auditado = auditado_robado
                        
                    if corp.auditado_robado != nuevo_auditado:
                        campos_cambiados.append(f"auditado_robado: {corp.auditado_robado} -> {nuevo_auditado}")
                        corp.auditado_robado = nuevo_auditado
                        tiene_cambios = True
                        
                    if url_prueba and corp.url_prueba != url_prueba: 
                        campos_cambiados.append(f"url_prueba: {corp.url_prueba} -> {url_prueba}")
                        corp.url_prueba = url_prueba
                        tiene_cambios = True
                        
                    if nota and corp.nota != nota: 
                        campos_cambiados.append(f"nota: {corp.nota} -> {nota}")
                        corp.nota = nota
                        tiene_cambios = True
                        
                    if age_raw and corp.age_raw != age_raw: 
                        campos_cambiados.append(f"age_raw: {corp.age_raw} -> {age_raw}")
                        corp.age_raw = age_raw
                        tiene_cambios = True
                        
                    if precio_cliente is not None and corp.precio_cliente != precio_cliente: 
                        campos_cambiados.append(f"precio_cliente: {corp.precio_cliente} -> {precio_cliente}")
                        corp.precio_cliente = precio_cliente
                        tiene_cambios = True
                        
                    if corp.status != status_val:
                        campos_cambiados.append(f"status: '{corp.status}' -> '{status_val}'")
                        corp.status = status_val
                        tiene_cambios = True
                        
                    if tiene_cambios:
                        corp.fuente_importacion = 'excel_inventario'
                        corp.fecha_importacion = datetime.now(timezone.utc)
                        corp.source_file = filename
                        db.session.add(corp)
                        operaciones_pendientes += 1
                        stats["actualizadas"] += 1
                        stats.setdefault("detalles_actualizadas", []).append({
                            "name": nombre_norm,
                            "state": codigo_estado,
                            "cambios": campos_cambiados
                        })
                    else:
                        stats["sin_cambios"] += 1
                        
                else:
                    # Nuevo
                    corp = Corporation(
                        name=nombre_norm,
                        state=codigo_estado,
                        status=status_val,
                        auditado_robado=auditado_robado,
                        url_prueba=url_prueba,
                        nota=nota,
                        age_raw=age_raw,
                        precio_cliente=precio_cliente,
                        fuente_importacion='excel_inventario',
                        fecha_importacion=datetime.now(timezone.utc),
                        source_file=filename
                    )
                    db.session.add(corp)
                    # Registrar en dict para evitar duplicados si aparece dos veces en el excel
                    dict_existentes[(nombre_norm, codigo_estado)] = corp
                    operaciones_pendientes += 1
                    stats["insertadas"] += 1
                    
                # Flush/Commit por lotes para rendimiento
                if operaciones_pendientes >= BATCH_SIZE:
                    if not modo_prueba:
                        db.session.commit()
                    else:
                        db.session.flush()
                    operaciones_pendientes = 0
                    
            except Exception as e:
                # Si hay error en el lote, hacemos rollback parcial si el driver lo permite o completo
                db.session.rollback()
                operaciones_pendientes = 0
                stats["errores"] += 1
                stats["detalles_errores"].append(f"Error procesando '{nombre_crudo}': {str(e)}")
                
    if not modo_prueba:
        try:
            if operaciones_pendientes > 0:
                db.session.commit()
        except Exception as e:
            db.session.rollback()
            stats["errores"] += 1
            stats["detalles_errores"].append(f"Error en el commit final: {str(e)}")
    else:
        db.session.rollback()
        
    return stats