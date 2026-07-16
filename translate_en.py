# Script to fill in all English translations in the PO file

translations = {
    # routes.py flash messages
    "Sesión iniciada correctamente.": "Session started successfully.",
    "Usuario o contraseña incorrectos.": "Incorrect username or password.",
    "Has cerrado sesión.": "You have been logged out.",
    "No se seleccionó ningún archivo.": "No file was selected.",
    "El archivo no tiene nombre.": "The file has no name.",
    "Solo se permiten archivos CSV (.csv).": "Only CSV files (.csv) are allowed.",
    "Error al procesar el archivo: %(e)s": "Error processing file: %(e)s",
    "Formato de fecha inválido: %(e)s": "Invalid date format: %(e)s",
    "No se encontraron registros para los filtros seleccionados.": "No records found for the selected filters.",
    "Nombre de archivo vacío.": "Empty file name.",
    "Error procesando archivo: %(e)s": "Error processing file: %(e)s",
    "%(state)s %(status)s.": "%(state)s %(status)s.",
    # Sidebar nav
    "Dashboard": "Dashboard",
    "Corporaciones": "Corporations",
    "Cargar CSV": "Upload CSV",
    "Ejecuciones": "Runs",
    "Reportes": "Reports",
    "Portales": "Portals",
    "Configuración": "Settings",
    "Ajustes": "Settings",
    "Próximo": "Next",
    "Progreso escaneo automático": "Auto-scan progress",
    "Escaneo Manual": "Manual Scan",
    # Topbar buttons
    "Cambiar a Inglés": "Switch to English",
    "Switch to Spanish": "Switch to Spanish",
    "Iniciar Tour": "Start Tour",
    "Ver Tour Guía": "View Guided Tour",
    "¿Cómo funciona?": "How does it work?",
    "Cambiar tema": "Toggle theme",
    "Cambiar Tema": "Toggle Theme",
    "Modo Oscuro": "Dark Mode",
    "Modo Claro": "Light Mode",
    "Cerrar Sesión": "Log Out",
    "Salir": "Log Out",
    # Corporations page
    "Corporaciones Cargadas": "Uploaded Corporations",
    "Listado de Corporaciones": "Corporation List",
    "Todos los estados": "All states",
    "Todos los estatus": "All statuses",
    "Corporación": "Corporation",
    "Estado": "State",
    "Estatus": "Status",
    "Prioridad": "Priority",
    "Fecha Registro": "Registration Date",
    "Fuente": "Source",
    "ID:": "ID:",
    "Anterior": "Previous",
    "Página": "Page",
    "de": "of",
    "total": "total",
    "Siguiente": "Next",
    "Sin corporaciones cargadas": "No corporations loaded",
    "Importa un archivo CSV para comenzar el monitoreo o inicia un escaneo para descubrir entidades automáticamente.": "Import a CSV file to start monitoring or start a scan to discover entities automatically.",
    "Cargar CSV ahora": "Upload CSV now",
    # Dashboard / index
    "Escaneo completado": "Scan completed",
    "Escaneo en progreso...": "Scan in progress...",
    "Escaneo fallido": "Scan failed",
    "Iniciado el": "Started on",
    "a las": "at",
    "Se procesaron": "Processed",
    "empresas, detectando": "companies, detecting",
    "con posible robo.": "with possible theft.",
    "Descargar Reporte": "Download Report",
    "Ver Detalle de Ejecución": "View Run Detail",
    "No hay escaneos recientes": "No recent scans",
    "Inicia un escaneo manual o espera a la ejecución programada.": "Start a manual scan or wait for the scheduled run.",
    "Total Cargadas": "Total Uploaded",
    "Pendientes de revisión": "Pending Review",
    "Limpias (Último Escaneo)": "Clean (Last Scan)",
    "Posible Robo (Último)": "Possible Theft (Last)",
    "Alertas Recientes": "Recent Alerts",
    # Login page
    "Inicio de sesión": "Login",
    "Iniciar Sesión": "Log In",
    "Control de acceso al sistema": "System access control",
    "Usuario": "Username",
    "Ingresa tu usuario": "Enter your username",
    "Contraseña": "Password",
    # Reports page
    "Reportes y Análisis": "Reports & Analysis",
    "Exportar Reporte Personalizado": "Export Custom Report",
    "Desde": "From",
    "Hasta": "To",
    "Formato": "Format",
    "Generar Reporte": "Generate Report",
    "Frecuencia de Alertas (Últimos 7 días)": "Alert Frequency (Last 7 days)",
    # Run detail
    "Ejecución": "Run",
    "Iniciada": "Started",
    "Finalizada": "Finished",
    "Duración": "Duration",
    "%(m)d min %(s)02d s": "%(m)d min %(s)02d s",
    "Disparada por": "Triggered by",
    "Procesadas": "Processed",
    "Alertas": "Alerts",
    "Errores": "Errors",
    "Descargar Excel": "Download Excel",
    "Resultados": "Results",
    "registros": "records",
    "Oficial": "Officer",
    "Agente Registrado": "Registered Agent",
    "Portal Status": "Portal Status",
    "Alerta": "Alert",
    "Cambio": "Change",
    "Evidencia": "Evidence",
    "Notas": "Notes",
    "Error": "Error",
    "OK": "OK",
    "Sin cambio": "No change",
    "Sin resultados": "No results",
    "Esta ejecución no tiene registros de escaneo aún.": "This run has no scan records yet.",
    # Runs list
    "Historial de Ejecuciones": "Run History",
    "Ejecuciones Diarias": "Daily Runs",
    "Fecha / Hora": "Date / Time",
    "Auto": "Auto",
    "Manual": "Manual",
    "Ver detalle": "View detail",
    "Página %(page)s de %(pages)s (%(total)s total)": "Page %(page)s of %(pages)s (%(total)s total)",
    "Sin ejecuciones registradas": "No runs recorded",
    "Realiza un escaneo manual o espera la ejecución automática diaria.": "Run a manual scan or wait for the daily automatic run.",
    "Iniciar escaneo ahora": "Start scan now",
    # States page
    "Portales por Estado": "Portals by State",
    "Portales de Búsqueda por Estado": "Search Portals by State",
    "Importar CSV": "Import CSV",
    "Scraper activo": "Active scraper",
    "Estado con scraper implementado (Fase 2)": "State with implemented scraper (Phase 2)",
    "Pendiente": "Pending",
    "URL configurada, scraper aún no implementado": "URL configured, scraper not yet implemented",
    "Prioridad MVP": "MVP Priority",
    "Código": "Code",
    "Portal URL": "Portal URL",
    "Scraper": "Scraper",
    "Activo": "Active",
    "Inactivo": "Inactive",
    "Desactivar": "Deactivate",
    "Activar": "Activate",
    "%(count)s estados configurados": "%(count)s states configured",
    "%(count)s con scraper activo": "%(count)s with active scraper",
    "%(count)s activos": "%(count)s active",
    "Sin portales configurados": "No portals configured",
    "Importar CSV de estados": "Import states CSV",
    # Upload page
    "Importar Corporaciones": "Import Corporations",
    "Arrastra tu CSV aquí": "Drag your CSV here",
    "o haz clic para seleccionar": "or click to select",
    "Solo archivos .csv · Máx. 16 MB": "Only .csv files · Max 16 MB",
    "Quitar archivo": "Remove file",
    "Formato esperado del CSV": "Expected CSV format",
    "Columna": "Column",
    "Requerido": "Required",
    "Descripción": "Description",
    "Ejemplo": "Example",
    "Sí": "Yes",
    "Nombre legal de la corporación": "Legal name of the corporation",
    "Código de estado (HI o CO)": "State code (HI or CO)",
    "Opcional": "Optional",
    "Disponible o Vendida": "Available or Sold",
    "ID en el portal estatal": "ID in state portal",
    "Fecha de registro": "Registration date",
    "Número entero (mayor = primero)": "Integer (higher = first)",
    "Primer criterio de detección": "First detection criterion",
    "Segundo criterio de detección": "Second detection criterion",
    "Descargar CSV de ejemplo": "Download sample CSV",
    # Sube un archivo CSV...
    "Sube un archivo CSV con la lista diaria de corporaciones a monitorear. Los registros con estatus <strong>Vendida</strong> se importarán pero serán excluidos del escaneo.": "Upload a CSV file with the daily list of corporations to monitor. Records with status <strong>Sold</strong> will be imported but excluded from the scan.",
    # States empty state
    "Importa el archivo CSV con el formato <strong>Estado[TAB]URL</strong> para configurar los portales de búsqueda.": "Import the CSV file with format <strong>State[TAB]URL</strong> to configure the search portals.",
}

import re

def fill_po(po_path, translations):
    with open(po_path, 'r', encoding='utf-8') as f:
        content = f.read()

    entries = re.split(r'\n\n', content)
    new_entries = []

    for entry in entries:
        msgid_match = re.search(r'^msgid "(.+?)"', entry, re.MULTILINE | re.DOTALL)
        msgstr_match = re.search(r'^msgstr ""$', entry, re.MULTILINE)

        if msgid_match and msgstr_match:
            # Unescape the msgid value
            raw_msgid = msgid_match.group(1)
            # Handle multiline msgid (joined with \n)
            msgid_decoded = raw_msgid.replace('\\n', '\n').replace('\\"', '"')

            if msgid_decoded in translations:
                translated = translations[msgid_decoded]
                escaped = translated.replace('"', '\\"').replace('\n', '\\n')
                entry = re.sub(r'^msgstr ""$', f'msgstr "{escaped}"', entry, flags=re.MULTILINE)

        new_entries.append(entry)

    with open(po_path, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(new_entries))

    print(f"Done. Processed {len(entries)} entries.")

if __name__ == '__main__':
    fill_po('translations/en/LC_MESSAGES/messages.po', translations)
