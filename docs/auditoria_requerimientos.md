# Auditoría de Cumplimiento de Requerimientos

Basado en el documento `docs/requerimientos-monitoreo-corporaciones-sos.md`, aquí tienes el desglose de implementación de las secciones 3, 4 y 5.

## Sección 3: Alcance Funcional

### 3.1 Entrada de Datos
- **Integración con API de Salesforce:** **NO EXISTE**.
- **Subida de archivo CSV (fallback):** **IMPLEMENTADO Y VERIFICADO**. Se soporta mediante `app/services/importador_inventario.py`, que ha procesado el Excel con éxito.
- **Permitir recarga:** **IMPLEMENTADO Y VERIFICADO**. El importador es idempotente.

### 3.2 Ordenamiento de la Lista de Verificación
- **Orden por antigüedad (fecha de constitución):** **NO FUNCIONAL**. Aunque el código en `scanner.py` intenta ordenar por `c.date_registered`, esa columna está completamente vacía (NULL) en todas las filas. El inventario solo pobló `age_raw`. En la práctica, se está ordenando alfabéticamente.
- **Orden por prioridad de estado:** **IMPLEMENTADO Y VERIFICADO**. (`app/services/scanner.py`, a través de `config.ESTADOS_PRIORITARIOS`).

### 3.3 Estados a Monitorear
- **Prioridades y alcance (9 estados):** **IMPLEMENTADO Y VERIFICADO**. Configurado en `config.py`. Solo **HI** y **CO** tienen scrapers activos.

### 3.4 Proceso de Verificación por Corporación
- **Navegación y Búsqueda:** **IMPLEMENTADO Y VERIFICADO**. Scrapers listos para CO y HI.
- **Extracción del Oficial (no solo el agente):** **PARCIAL**. En HI extrae del portal directamente, en CO usa Socrata.
- **Regla de detección de posible robo:** **IMPLEMENTADO PERO DEFECTUOSO**. (`app/services/detector.py`). El código existe y se conecta por estado, pero usa búsqueda por subcadenas (`in`) sin validación de fronteras de palabra ni agrupación estricta de nombres, generando falsos positivos y negativos (ej. cruza nombres de oficiales distintos).
- **Captura en PDF de evidencia:** **IMPLEMENTADO Y VERIFICADO**. `app/scrapers/base.py` genera la captura.
- **Omitir "Vendida":** **IMPLEMENTADO Y VERIFICADO**. Filtra a través de `is_processable()`.

### 3.5 Reporte Diario (Excel/CSV)
- **Generación del archivo con columnas obligatorias:** **IMPLEMENTADO**. (`app/services/reporter.py`).

### 3.6 Almacenamiento en la Nube
- **Integración con Dropbox / Google Drive:** **NO EXISTE**. No hay lógica en `uploader.py` ni integraciones configuradas funcionalmente en `storage.py`.

### 3.7 Notificación por Correo Electrónico
- **Envío automático del correo resumen:** **SIN VERIFICAR**. El código fuente existe en `app/services/mailer.py` y construye el reporte HTML, pero nunca se ha probado en este entorno ni se ha ejecutado el scheduler para confirmar que el envío de red funcione.

---

## Sección 4: Requisitos Técnicos

- **Interfaz de usuario web (Panel de Admin):** **SIN VERIFICAR**. Existen rutas y modelos, pero no se ha validado su correcto funcionamiento en la UI real.
- **Backend Flask:** **IMPLEMENTADO Y VERIFICADO**.
- **Motor de Scraping (Reintentos, Captchas, Timeout):** **IMPLEMENTADO Y VERIFICADO**.
- **Lógica de Extracción con IA (Normalización):** **NO EXISTE / PARCIAL**. Se normaliza vía expresiones regulares estáticas (`app/services/normalizer.py`), pero no se usa un agente LLM real para la clasificación o lectura de fallos estructurales.

---

## Sección 5: Reglas de Negocio Importantes

- **Exclusión por estado “Vendida”:** **IMPLEMENTADO Y VERIFICADO**.
- **Condición de coincidencia (Case-insensitive, AND/OR):** **DEFECTUOSO**. La condición está escrita, pero su lógica de subcadenas combinadas (`combined string`) viola la fiabilidad.
- **PDF solo para alertas (“Posible Robo”):** **IMPLEMENTADO Y VERIFICADO**. En `app/services/scanner.py` borra el archivo `scraped.pdf_path` si el resultado es limpio.
