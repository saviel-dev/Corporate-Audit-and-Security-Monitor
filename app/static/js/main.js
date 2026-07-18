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

    if (data.running) {
      if (btnManualScan && !btnManualScan.disabled) {
        btnManualScan.disabled = true;
        btnManualScan.style.opacity = '0.7';
        btnManualScan.innerHTML = '<l-bouncy size="20" speed="1.75" color="#ffffff"></l-bouncy> Escaneando...';
        if (window.lucide) lucide.createIcons();
      }
    } else {
      if (btnManualScan && btnManualScan.disabled) {
        btnManualScan.disabled = false;
        btnManualScan.style.opacity = '1';
        btnManualScan.innerHTML = '<i data-lucide="play-circle"></i> Escaneo Manual';
        if (window.lucide) lucide.createIcons();
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
      let steps = [];
      
      // 1. Dashboard Page
      if (document.getElementById('last-run-banner')) {
        steps = [
          { popover: { title: '¡Bienvenido!', description: 'Este es el Panel de Control. Vamos a dar un rápido recorrido por las herramientas principales.', side: 'bottom', align: 'start' } },
          { element: '#sidebar', popover: { title: 'Navegación', description: 'Aquí puedes moverte entre el Dashboard, la lista de Corporaciones, cargar archivos CSV y ver historiales de ejecución.', side: 'right', align: 'start' } },
          { element: '#last-run-banner', popover: { title: 'Estado del Escaneo', description: 'Este banner te informa sobre el último escaneo general realizado por el sistema.', side: 'bottom', align: 'start' } },
          { element: '.stats-grid', popover: { title: 'Resumen Rápido', description: 'Un vistazo a los números totales: empresas cargadas, pendientes, limpias y posibles incidencias.', side: 'top', align: 'center' } },
          { element: '#recent-alerts-section', popover: { title: 'Alertas Recientes', description: 'Cualquier empresa que genere una alerta de riesgo aparecerá en esta lista para tu pronta revisión.', side: 'top', align: 'start' } },
          { element: '#btn-manual-scan', popover: { title: 'Escaneo Manual', description: 'Si necesitas forzar una revisión inmediata de los portales, usa este botón.', side: 'right', align: 'end' } },
          { element: '#theme-toggle', popover: { title: 'Configuraciones Visuales', description: 'Puedes alternar entre modo oscuro y claro según tu preferencia en cualquier momento.', side: 'left', align: 'start' } }
        ];
      }
      // 2. Corporations List Page
      else if (document.getElementById('corporations-section')) {
        steps = [
          { popover: { title: 'Sección Corporaciones', description: 'Aquí gestionamos las entidades del sistema y vigilamos que su información legal no sea manipulada.', side: 'bottom', align: 'start' } },
          { element: '#corporations-section', popover: { title: 'Listado de Empresas', description: 'En esta tabla se muestran las corporaciones. Cada una se audita diariamente comparando su información de registro oficial con las reglas de detección del sistema.', side: 'top', align: 'start' } },
          { element: '#filter-form', popover: { title: 'Filtros y Búsqueda', description: 'Puedes aislar corporaciones por su estado (Hawaii o Colorado) o su disponibilidad comercial (Disponible/Vendida).', side: 'bottom', align: 'end' } },
          { element: document.getElementById('btn-upload-nav') ? '#btn-upload-nav' : '#empty-state', popover: { title: 'Importar Nuevos Registros', description: 'Si tienes un listado de nuevas corporaciones para vigilar, usa esta herramienta de carga para subirlas mediante archivos CSV.', side: 'left', align: 'center' } }
        ];
      }
      // 3. Upload CSV Page
      else if (document.getElementById('upload-page')) {
        steps = [
          { popover: { title: 'Importación de Datos', description: 'Esta pantalla te permite cargar de manera masiva las empresas que deseas vigilar en el monitor.', side: 'bottom', align: 'start' } },
          { element: '#drop-zone', popover: { title: 'Área de Carga', description: 'Arrastra y suelta tu archivo CSV aquí, o haz clic para seleccionarlo desde tus documentos.', side: 'bottom', align: 'center' } },
          { element: '#format-guide', popover: { title: 'Guía de Columnas', description: 'Asegúrate de que tu archivo cuente con las cabeceras requeridas. Puedes descargar la plantilla para evitar errores de formato.', side: 'top', align: 'start' } }
        ];
      }
      // 4. Run Details Page
      else if (document.getElementById('run-detail-header')) {
        steps = [
          { popover: { title: 'Detalle de Ejecución', description: 'Aquí verás el desglose minucioso de un escaneo diario específico.', side: 'bottom', align: 'start' } },
          { element: '#run-detail-header', popover: { title: 'Métricas de la Corrida', description: 'Resumen de fecha de inicio, duración, cantidad de empresas procesadas, alertas y errores encontrados.', side: 'bottom', align: 'center' } },
          { element: '#results-section', popover: { title: 'Auditoría Corporativa', description: 'Tabla comparativa con el nombre del oficial oficial en el portal de registro del estado. Si se encuentra un cambio de agente o directivo no autorizado, se encenderá una alerta.', side: 'top', align: 'start' } }
        ];
        if (document.getElementById('btn-download-excel')) {
          steps.splice(2, 0, { element: '#btn-download-excel', popover: { title: 'Reporte Excel', description: 'Haz clic aquí para descargar un reporte ordenado de este escaneo en formato XLSX.', side: 'left', align: 'center' } });
        }
      }
      // 5. Runs List Page
      else if (document.getElementById('runs-section')) {
        steps = [
          { popover: { title: 'Historial de Ejecuciones', description: 'Lista de todos los escaneos automatizados y manuales que ha completado el sistema.', side: 'bottom', align: 'start' } },
          { element: '#runs-table', popover: { title: 'Tabla de Historial', description: 'Permite auditar el rendimiento del robot, ver cuántas alertas se generaron y cuánto demoró cada escaneo.', side: 'top', align: 'start' } }
        ];
        if (document.querySelector('#runs-table .btn-icon')) {
          steps.push({ element: '#runs-table .btn-icon', popover: { title: 'Reporte Detallado', description: 'Usa el icono del ojo para navegar al desglose individual de dicha ejecución y analizar la evidencia de cada alerta.', side: 'left', align: 'center' } });
        }
      }
      // 6. States Portals Page
      else if (document.getElementById('states-section')) {
        steps = [
          { popover: { title: 'Configuración de Portales', description: 'Aquí visualizas los estados del país que están registrados en tu sistema de monitor.', side: 'bottom', align: 'start' } },
          { element: '#states-legend', popover: { title: 'Estado del Scraper', description: 'Indica qué estados tienen un robot activo configurado (por ejemplo, Hawaii o Colorado) y cuáles siguen pendientes.', side: 'bottom', align: 'start' } },
          { element: '#states-table', popover: { title: 'Lista de Búsqueda', description: 'URLs oficiales que utiliza el sistema para rastrear las empresas. Puedes activar o desactivar la consulta a cualquier portal individualmente.', side: 'top', align: 'start' } },
          { element: document.getElementById('btn-import-states') ? '#btn-import-states' : '#empty-states', popover: { title: 'Importar Portales', description: 'Si necesitas configurar o actualizar los enlaces de búsqueda estatales de forma masiva, sube un CSV aquí.', side: 'left', align: 'center' } }
        ];
      }
      // 7. Reports Page
      else if (document.getElementById('reports-page')) {
        steps = [
          { popover: { title: 'Análisis y Reportes', description: 'Esta sección te permite auditar las estadísticas de seguridad e imprimir reportes consolidados.', side: 'bottom', align: 'start' } },
          { element: '#report-generator-card', popover: { title: 'Exportación a Medida', description: 'Configura filtros por estado, rango de fechas y formato (Excel, PDF, CSV) para exportar reportes.', side: 'bottom', align: 'center' } },
          { element: '#chart-alerts-card', popover: { title: 'Frecuencia de Alertas', description: 'Este gráfico ilustra la cantidad diaria de posibles robos de identidad detectados en la última semana.', side: 'top', align: 'center' } },
          { element: '#chart-states-card', popover: { title: 'Distribución por Estado', description: 'Muestra de forma rápida cuántas corporaciones estás monitoreando activamente en Hawaii vs. Colorado.', side: 'top', align: 'center' } },
          { element: '#history-reports-card', popover: { title: 'Historial de Descargas', description: 'Aquí tienes un registro de los reportes generados anteriormente con enlaces directos para descargarlos de nuevo.', side: 'top', align: 'start' } }
        ];
      }

      if (steps.length > 0) {
        const driverObj = window.driver.js.driver({
          showProgress: true,
          nextBtnText: 'Siguiente &rarr;',
          prevBtnText: '&larr; Anterior',
          doneBtnText: 'Terminar',
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
