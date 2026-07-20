document.addEventListener('DOMContentLoaded', () => {

  // Live clock in topbar (updates every second)
  const timeEl = document.getElementById('topbar-time');
  const dateEl = document.getElementById('topbar-date');
  // Detect current language from cookie
  const langCookie = document.cookie.split(';').map(c => c.trim()).find(c => c.startsWith('lang='));
  const currentLang = langCookie ? langCookie.split('=')[1] : 'en';
  const clockLocale = currentLang === 'en' ? 'en-US' : 'es-ES';

  if (timeEl && dateEl) {
    const update = () => {
      const now = new Date();
      const hours = String(now.getHours()).padStart(2, '0');
      const minutes = String(now.getMinutes()).padStart(2, '0');
      const seconds = String(now.getSeconds()).padStart(2, '0');
      timeEl.textContent = `${hours}:${minutes}:${seconds}`;

      const weekday = now.toLocaleDateString(clockLocale, { weekday: 'short' }).replace('.', '');
      const day = now.getDate();
      const month = now.toLocaleDateString(clockLocale, { month: 'short' }).replace('.', '');
      dateEl.textContent = `${weekday}, ${day} ${month}`.toUpperCase();
    };
    update();
    setInterval(update, 1000);
  }

  // Sidebar toggle (mobile)
  const toggleBtn = document.getElementById('sidebar-toggle');
  const sidebar   = document.getElementById('sidebar');
  if (toggleBtn && sidebar) {
    toggleBtn.addEventListener('click', () => sidebar.classList.toggle('open'));
    document.addEventListener('click', (e) => {
      if (!sidebar.contains(e.target) && !toggleBtn.contains(e.target)) {
        sidebar.classList.remove('open');
      }
    });
  }

  // Auto-dismiss flash messages after 5s
  const flashContainer = document.getElementById('flash-container');
  if (flashContainer) {
    setTimeout(() => {
      flashContainer.style.transition = 'opacity 0.4s';
      flashContainer.style.opacity = '0';
      setTimeout(() => flashContainer.remove(), 400);
    }, 5000);
  }

  // ── Upload drag & drop ─────────────────────────────────────────────────
  const dropZone  = document.getElementById('drop-zone');
  const fileInput = document.getElementById('file-input');
  const dzContent = document.getElementById('drop-zone-content');
  const dzPreview = document.getElementById('drop-preview');
  const previewFn = document.getElementById('preview-filename');
  const previewSz = document.getElementById('preview-size');
  const clearBtn  = document.getElementById('preview-clear');
  const submitBtn = document.getElementById('btn-upload-submit');

  function formatBytes(b) {
    if (b < 1024) return b + ' B';
    if (b < 1024 * 1024) return (b / 1024).toFixed(1) + ' KB';
    return (b / (1024 * 1024)).toFixed(1) + ' MB';
  }

  function showPreview(file) {
    if (!dzContent || !dzPreview) return;
    previewFn.textContent = file.name;
    previewSz.textContent = formatBytes(file.size);
    dzContent.style.display = 'none';
    dzPreview.style.display  = 'flex';
    if (submitBtn) submitBtn.disabled = false;
    if (window.lucide) lucide.createIcons();
  }

  function clearPreview() {
    if (!dzContent || !dzPreview) return;
    dzContent.style.display = '';
    dzPreview.style.display  = 'none';
    if (fileInput) fileInput.value = '';
    if (submitBtn) submitBtn.disabled = true;
  }

  if (fileInput) {
    fileInput.addEventListener('change', () => {
      if (fileInput.files.length > 0) showPreview(fileInput.files[0]);
    });
  }

  if (clearBtn) {
    clearBtn.addEventListener('click', (e) => {
      e.preventDefault(); e.stopPropagation();
      clearPreview();
    });
  }

  if (dropZone) {
    ['dragenter', 'dragover'].forEach(evt =>
      dropZone.addEventListener(evt, (e) => { e.preventDefault(); dropZone.classList.add('drag-over'); })
    );
    ['dragleave', 'drop'].forEach(evt =>
      dropZone.addEventListener(evt, () => dropZone.classList.remove('drag-over'))
    );
    dropZone.addEventListener('drop', (e) => {
      e.preventDefault();
      const files = e.dataTransfer.files;
      if (files.length > 0 && files[0].name.endsWith('.csv')) {
        const dt = new DataTransfer();
        dt.items.add(files[0]);
        fileInput.files = dt.files;
        showPreview(files[0]);
      }
    });
  }

  // ── Scan Progress WebSocket ──────────────────────────────────────────────
  const progressContainer = document.getElementById('scan-progress-container');
  const progressText = document.getElementById('scan-progress-text');
  const progressBar = document.getElementById('scan-progress-bar');
  const btnManualScan = document.getElementById('btn-manual-scan');

  function updateScanUI(data) {
    if (progressContainer && progressText && progressBar) {
      if (!data.running && data.status === 'done') {
        progressText.textContent = "Escaneo Completo";
        progressBar.style.width = "100%";
        progressBar.style.background = "var(--success, #22c55e)";
      } else {
        let processed = data.processed || 0;
        let expected = data.expected || 1; 
        
        // Expected could grow if discovery is running, so max it if needed
        if (processed > expected) expected = processed;
        
        let percentage = (processed / expected) * 100;
        if (percentage > 100) percentage = 100;

        progressText.textContent = `${processed} / ${expected}`;
        progressBar.style.width = `${percentage}%`;
        progressBar.style.background = "var(--primary)";
      }
    }

    const formManual = document.getElementById('form-manual-scan');
    const formCancel = document.getElementById('form-cancel-scan');
    const formResume = document.getElementById('form-resume-scan');

    if (data.running) {
      if (formManual) formManual.style.display = 'none';
      if (formCancel) formCancel.style.display = 'block';
      if (formResume) formResume.style.display = 'none';
    } else {
      if (formCancel) formCancel.style.display = 'none';
      
      if (data.resumable_run_id) {
        if (formManual) formManual.style.display = 'block';
        if (formResume) {
          formResume.style.display = 'block';
          formResume.action = '/scan/resume/' + data.resumable_run_id;
        }
      } else {
        if (formManual) formManual.style.display = 'block';
        if (formResume) formResume.style.display = 'none';
      }
    }

    // 3. Run Detail Page real-time updates
    const runHeader = document.getElementById('run-detail-header');
    if (runHeader && data.run_id) {
      const currentRunId = runHeader.getAttribute('data-run-id');
      if (currentRunId === String(data.run_id)) {
        const processedEl = document.getElementById('detail-processed');
        const alertsEl = document.getElementById('detail-alerts');
        const errorsEl = document.getElementById('detail-errors');
        const statusEl = document.getElementById('detail-status');
        
        if (processedEl) processedEl.textContent = data.processed;
        if (alertsEl) alertsEl.textContent = data.alerts || 0;
        if (errorsEl) errorsEl.textContent = data.errors || 0;
        
        if (statusEl) {
          statusEl.textContent = data.status;
          statusEl.className = 'run-status-badge run-status-badge--' + data.status;
          
          // Auto-refresh the page once it finishes to show the results table
          if (data.status === 'done' && !window.runReloaded) {
             window.runReloaded = true;
             setTimeout(() => window.location.reload(), 1500);
          }
        }
      }
    }
  }

  // 1. Initial State Fetch (run once)
  if (progressContainer && progressText && progressBar) {
    fetch('/api/scan_status')
      .then(res => res.json())
      .then(data => updateScanUI(data))
      .catch(err => console.error("Error fetching scan status:", err));
  }

  // 2. Real-time Updates via Socket.IO
  if (window.io) {
    const socket = io();
    socket.on('scan_progress', function(data) {
      updateScanUI(data);
    });
  }

  // ── Stat Numbers Animation (Count Up) ──────────────────────────────────
  const statValues = document.querySelectorAll('.stat-value');
  const hasAnimatedStats = sessionStorage.getItem('statsAnimated');

  statValues.forEach(el => {
    const targetText = el.textContent.trim();
    const target = parseInt(targetText, 10);
    
    if (!isNaN(target) && target > 0) {
      if (!hasAnimatedStats) {
        // Animate only on first load
        el.textContent = '0';
        const duration = 1500; // 1.5 seconds
        const startTime = performance.now();

        const updateCounter = (currentTime) => {
          const elapsedTime = currentTime - startTime;
          let progress = elapsedTime / duration;
          if (progress > 1) progress = 1;

          // ease-out cubic
          const easeOut = 1 - Math.pow(1 - progress, 3);
          const current = Math.floor(target * easeOut);

          el.textContent = current;

          if (progress < 1) {
            requestAnimationFrame(updateCounter);
          } else {
            el.textContent = targetText; 
          }
        };
        requestAnimationFrame(updateCounter);
      } else {
        // Show immediately if already animated this session
        el.textContent = targetText;
      }
    }
  });

  if (!hasAnimatedStats) {
    sessionStorage.setItem('statsAnimated', 'true');
  }

  // ── Theme Toggle ──────────────────────────────────────────────────────────
  const themeToggle = document.getElementById('theme-toggle');
  const iconLight = document.getElementById('theme-icon-light');
  const iconDark = document.getElementById('theme-icon-dark');
  const themeText = document.getElementById('theme-text');
  
  if (themeToggle && iconLight && iconDark) {
    const updateThemeUI = (isLightMode) => {
      if (isLightMode) {
        iconLight.style.display = 'none';
        iconDark.style.display = 'inline-block';
        // Read translated text from data-attribute
        if (themeText) themeText.textContent = themeText.dataset.lightText || 'Dark Mode';
      } else {
        iconLight.style.display = 'inline-block';
        iconDark.style.display = 'none';
        // Read translated text from data-attribute
        if (themeText) themeText.textContent = themeText.dataset.darkText || 'Light Mode';
      }
      if (window.lucide) lucide.createIcons();
    };

    const isLight = document.documentElement.classList.contains('theme-light');
    updateThemeUI(isLight);

    themeToggle.addEventListener('click', () => {
      document.documentElement.classList.toggle('theme-light');
      const lightActive = document.documentElement.classList.contains('theme-light');
      localStorage.setItem('theme', lightActive ? 'light' : 'dark');
      updateThemeUI(lightActive);
    });
  }

  // ── Driver.js Interactive Tours ──────────────────────────────────────────
  const btnTour = document.getElementById('btn-tour');
  if (btnTour && window.driver) {
    btnTour.addEventListener('click', () => {
      const lang = document.documentElement.lang || 'es';
      const t = (esStr, enStr) => lang === 'en' ? enStr : esStr;

      let steps = [];
      
      // 1. Dashboard Page
      if (document.getElementById('last-run-banner')) {
        steps = [
          { popover: { title: t('¡Bienvenido!', 'Welcome!'), description: t('Este es el Panel de Control. Vamos a dar un rápido recorrido por las herramientas principales.', 'This is the Dashboard. Let\'s take a quick tour of the main tools.'), side: 'bottom', align: 'start' } },
          { element: '#sidebar', popover: { title: t('Navegación', 'Navigation'), description: t('Aquí puedes moverte entre el Dashboard, la lista de Corporaciones, cargar archivos CSV y ver historiales de ejecución.', 'Here you can move between the Dashboard, the Corporations list, upload CSV files, and view run histories.'), side: 'right', align: 'start' } },
          { element: '#last-run-banner', popover: { title: t('Estado del Escaneo', 'Scan Status'), description: t('Este banner te informa sobre el último escaneo general realizado por el sistema.', 'This banner informs you about the last general scan performed by the system.'), side: 'bottom', align: 'start' } },
          { element: '.stats-grid', popover: { title: t('Resumen Rápido', 'Quick Summary'), description: t('Un vistazo a los números totales: empresas cargadas, pendientes, limpias y posibles incidencias.', 'A glance at the total numbers: loaded, pending, clean companies, and potential incidents.'), side: 'top', align: 'center' } },
          { element: '#recent-alerts-section', popover: { title: t('Alertas Recientes', 'Recent Alerts'), description: t('Cualquier empresa que genere una alerta de riesgo aparecerá en esta lista para tu pronta revisión.', 'Any company that generates a risk alert will appear in this list for your prompt review.'), side: 'top', align: 'start' } },
          { element: '#btn-manual-scan', popover: { title: t('Escaneo Manual', 'Manual Scan'), description: t('Si necesitas forzar una revisión inmediata de los portales, usa este botón.', 'If you need to force an immediate review of the portals, use this button.'), side: 'right', align: 'end' } },
          { element: '#theme-toggle', popover: { title: t('Configuraciones Visuales', 'Visual Settings'), description: t('Puedes alternar entre modo oscuro y claro según tu preferencia en cualquier momento.', 'You can toggle between dark and light mode according to your preference at any time.'), side: 'left', align: 'start' } }
        ];
      }
      // 2. Corporations List Page
      else if (document.getElementById('corporations-section')) {
        steps = [
          { popover: { title: t('Sección Corporaciones', 'Corporations Section'), description: t('Aquí gestionamos las entidades del sistema y vigilamos que su información legal no sea manipulada.', 'Here we manage the system entities and monitor that their legal information is not manipulated.'), side: 'bottom', align: 'start' } },
          { element: '#corporations-section', popover: { title: t('Listado de Empresas', 'Company List'), description: t('En esta tabla se muestran las corporaciones. Cada una se audita diariamente comparando su información de registro oficial con las reglas de detección del sistema.', 'This table shows the corporations. Each one is audited daily by comparing its official registration information with the system\'s detection rules.'), side: 'top', align: 'start' } },
          { element: '#filter-form', popover: { title: t('Filtros y Búsqueda', 'Filters and Search'), description: t('Puedes aislar corporaciones por su estado (Hawaii o Colorado) o su disponibilidad comercial (Disponible/Vendida).', 'You can isolate corporations by their state (Hawaii or Colorado) or their commercial availability (Available/Sold).'), side: 'bottom', align: 'end' } },
          { element: document.getElementById('btn-upload-nav') ? '#btn-upload-nav' : '#empty-state', popover: { title: t('Importar Nuevos Registros', 'Import New Records'), description: t('Si tienes un listado de nuevas corporaciones para vigilar, usa esta herramienta de carga para subirlas mediante archivos CSV.', 'If you have a list of new corporations to monitor, use this upload tool to upload them via CSV files.'), side: 'left', align: 'center' } }
        ];
      }
      // 3. Upload CSV Page
      else if (document.getElementById('upload-page')) {
        steps = [
          { popover: { title: t('Importación de Datos', 'Data Import'), description: t('Esta pantalla te permite cargar de manera masiva las empresas que deseas vigilar en el monitor.', 'This screen allows you to mass upload the companies you want to monitor.'), side: 'bottom', align: 'start' } },
          { element: '#drop-zone', popover: { title: t('Área de Carga', 'Upload Area'), description: t('Arrastra y suelta tu archivo CSV aquí, o haz clic para seleccionarlo desde tus documentos.', 'Drag and drop your CSV file here, or click to select it from your documents.'), side: 'bottom', align: 'center' } },
          { element: '#format-guide', popover: { title: t('Guía de Columnas', 'Columns Guide'), description: t('Asegúrate de que tu archivo cuente con las cabeceras requeridas. Puedes descargar la plantilla para evitar errores de formato.', 'Make sure your file has the required headers. You can download the template to avoid formatting errors.'), side: 'top', align: 'start' } }
        ];
      }
      // 4. Run Details Page
      else if (document.getElementById('run-detail-header')) {
        steps = [
          { popover: { title: t('Detalle de Ejecución', 'Run Detail'), description: t('Aquí verás el desglose minucioso de un escaneo diario específico.', 'Here you will see the detailed breakdown of a specific daily scan.'), side: 'bottom', align: 'start' } },
          { element: '#run-detail-header', popover: { title: t('Métricas de la Corrida', 'Run Metrics'), description: t('Resumen de fecha de inicio, duración, cantidad de empresas procesadas, alertas y errores encontrados.', 'Summary of start date, duration, number of companies processed, alerts and errors found.'), side: 'bottom', align: 'center' } },
          { element: '#results-section', popover: { title: t('Auditoría Corporativa', 'Corporate Audit'), description: t('Tabla comparativa con el nombre del oficial oficial en el portal de registro del estado. Si se encuentra un cambio de agente o directivo no autorizado, se encenderá una alerta.', 'Comparative table with the official officer\'s name on the state registry portal. If an unauthorized agent or director change is found, an alert will be triggered.'), side: 'top', align: 'start' } }
        ];
        if (document.getElementById('btn-download-excel')) {
          steps.splice(2, 0, { element: '#btn-download-excel', popover: { title: t('Reporte Excel', 'Excel Report'), description: t('Haz clic aquí para descargar un reporte ordenado de este escaneo en formato XLSX.', 'Click here to download a sorted report of this scan in XLSX format.'), side: 'left', align: 'center' } });
        }
      }
      // 5. Runs List Page
      else if (document.getElementById('runs-section')) {
        steps = [
          { popover: { title: t('Historial de Ejecuciones', 'Run History'), description: t('Lista de todos los escaneos automatizados y manuales que ha completado el sistema.', 'List of all automated and manual scans completed by the system.'), side: 'bottom', align: 'start' } },
          { element: '#runs-table', popover: { title: t('Tabla de Historial', 'History Table'), description: t('Permite auditar el rendimiento del robot, ver cuántas alertas se generaron y cuánto demoró cada escaneo.', 'Allows auditing the robot\'s performance, seeing how many alerts were generated and how long each scan took.'), side: 'top', align: 'start' } }
        ];
        if (document.querySelector('#runs-table .btn-icon')) {
          steps.push({ element: '#runs-table .btn-icon', popover: { title: t('Reporte Detallado', 'Detailed Report'), description: t('Usa el icono del ojo para navegar al desglose individual de dicha ejecución y analizar la evidencia de cada alerta.', 'Use the eye icon to navigate to the individual breakdown of that run and analyze the evidence for each alert.'), side: 'left', align: 'center' } });
        }
      }
      // 6. States Portals Page
      else if (document.getElementById('states-section')) {
        steps = [
          { popover: { title: t('Configuración de Portales', 'Portals Configuration'), description: t('Aquí visualizas los estados del país que están registrados en tu sistema de monitor.', 'Here you view the country states registered in your monitor system.'), side: 'bottom', align: 'start' } },
          { element: '#states-legend', popover: { title: t('Estado del Scraper', 'Scraper Status'), description: t('Indica qué estados tienen un robot activo configurado (por ejemplo, Hawaii o Colorado) y cuáles siguen pendientes.', 'Indicates which states have an active robot configured (e.g. Hawaii or Colorado) and which ones are pending.'), side: 'bottom', align: 'start' } },
          { element: '#states-table', popover: { title: t('Lista de Búsqueda', 'Search List'), description: t('URLs oficiales que utiliza el sistema para rastrear las empresas. Puedes activar o desactivar la consulta a cualquier portal individualmente.', 'Official URLs used by the system to track companies. You can enable or disable queries to any portal individually.'), side: 'top', align: 'start' } },
          { element: document.getElementById('btn-import-states') ? '#btn-import-states' : '#empty-states', popover: { title: t('Importar Portales', 'Import Portals'), description: t('Si necesitas configurar o actualizar los enlaces de búsqueda estatales de forma masiva, sube un CSV aquí.', 'If you need to mass configure or update state search links, upload a CSV here.'), side: 'left', align: 'center' } }
        ];
      }
      // 7. Reports Page
      else if (document.getElementById('reports-page')) {
        steps = [
          { popover: { title: t('Análisis y Reportes', 'Analysis & Reports'), description: t('Esta sección te permite auditar las estadísticas de seguridad e imprimir reportes consolidados.', 'This section allows you to audit security statistics and print consolidated reports.'), side: 'bottom', align: 'start' } },
          { element: '#report-generator-card', popover: { title: t('Exportación a Medida', 'Custom Export'), description: t('Configura filtros por estado, rango de fechas y formato (Excel, PDF, CSV) para exportar reportes.', 'Configure filters by state, date range, and format (Excel, PDF, CSV) to export reports.'), side: 'bottom', align: 'center' } },
          { element: '#chart-alerts-card', popover: { title: t('Frecuencia de Alertas', 'Alerts Frequency'), description: t('Este gráfico ilustra la cantidad diaria de posibles robos de identidad detectados en la última semana.', 'This chart illustrates the daily amount of potential identity thefts detected in the last week.'), side: 'top', align: 'center' } },
          { element: '#chart-states-card', popover: { title: t('Distribución por Estado', 'Distribution by State'), description: t('Muestra de forma rápida cuántas corporaciones estás monitoreando activamente en Hawaii vs. Colorado.', 'Quickly shows how many corporations you are actively monitoring in Hawaii vs. Colorado.'), side: 'top', align: 'center' } },
          { element: '#history-reports-card', popover: { title: t('Historial de Descargas', 'Downloads History'), description: t('Aquí tienes un registro de los reportes generados anteriormente con enlaces directos para descargarlos de nuevo.', 'Here you have a record of previously generated reports with direct links to download them again.'), side: 'top', align: 'start' } }
        ];
      }

      if (steps.length > 0) {
        const driverObj = window.driver.js.driver({
          showProgress: true,
          nextBtnText: t('Siguiente &rarr;', 'Next &rarr;'),
          prevBtnText: t('&larr; Anterior', '&larr; Previous'),
          doneBtnText: t('Terminar', 'Done'),
          steps: steps
        });
        driverObj.drive();
      }
    });
  }

  // ── Sidebar Collapse Toggle ──────────────────────────────────────────────
  const collapseBtn = document.getElementById('sidebar-collapse-btn');
  const collapseIcon = document.getElementById('collapse-icon');
  
  if (collapseBtn && collapseIcon) {
    // Initial icon state
    if (document.documentElement.classList.contains('sidebar-collapsed')) {
      collapseIcon.setAttribute('data-lucide', 'minus');
    }
    
    collapseBtn.addEventListener('click', () => {
      document.documentElement.classList.toggle('sidebar-collapsed');
      const isCollapsed = document.documentElement.classList.contains('sidebar-collapsed');
      localStorage.setItem('sidebar-collapsed', isCollapsed ? 'true' : 'false');
      
      if (isCollapsed) {
        collapseIcon.setAttribute('data-lucide', 'minus');
      } else {
        collapseIcon.setAttribute('data-lucide', 'menu');
      }
      if (window.lucide) lucide.createIcons();
    });
  }

});
