# 📋 Documento de Levantamiento de Requerimientos  
## Sistema de Monitoreo y Detección de Corporaciones Robadas  
**Versión:** 1.0  
**Fecha:** 2026-07-20  
**Prioridad:** Urgente – Alta  

---

## 1. Resumen Ejecutivo

Se requiere una aplicación web que audite diariamente los registros corporativos en los sitios de la Secretaría de Estado de varios estados de EE. UU. para identificar cambios no autorizados en la titularidad o representación legal de las entidades. La herramienta debe alertar sobre posibles robos corporativos cuando los nombres de los funcionarios no coincidan con los esperados, generar evidencia en PDF y reportes, y automatizar el envío de resúmenes por correo electrónico.

---

## 2. Objetivo del Proyecto

Desarrollar una aplicación full‑stack con capacidad de scraping inteligente, integración de almacenamiento en la nube y notificaciones, que realice las siguientes tareas diarias:

1. Recibir una lista de corporaciones a verificar (con nombre, estado y situación operativa).
2. Ordenar la lista por antigüedad (más antigua primero) y prioridad del estado.
3. Para cada corporación en estado **“Disponible”**, consultar su registro en el sitio web de la Secretaría de Estado correspondiente.
4. Extraer el nombre del Presidente/Oficial y del Agente Registrado.
5. Verificar si el nombre del oficial contiene **“Marcio”** **Y** (“García” **o** “Andrade”); si **no** cumple, marcar la corporación como **“Posible Robo”**.
6. Guardar una instantánea en PDF del registro oficial cuando se detecte un cambio (marca).
7. Generar un archivo diario (Excel/CSV) con el resultado de todas las verificaciones.
8. Almacenar los PDF generados y los reportes en Dropbox o Google Drive, organizados por fecha.
9. Enviar un correo electrónico diario con el resumen de corporaciones marcadas.
10. **Excluir permanentemente cualquier corporación cuyo estado sea “Vendida”**, incluso si se detectaran cambios.

---

## 3. Alcance Funcional

### 3.1 Entrada de Datos

- **Opción preferente:** Integración con API de Salesforce para obtener en tiempo real la lista de corporaciones (nombre, estado, situación).
- **Opción alternativa (fallback):** Subida de un archivo CSV con columnas:
  - `Nombre de la corporación`
  - `Estado` (abreviatura oficial, ej. HI, CO)
  - `Estado operativo` (solo se procesarán las marcadas como “Disponible”; las “Vendida” se ignorarán).
- La herramienta debe permitir la recarga o actualización del archivo de entrada en cualquier momento.

### 3.2 Ordenamiento de la Lista de Verificación

- **Primer criterio:** Antigüedad de la corporación (de la más antigua a la más reciente). La fuente deberá proveer la fecha de constitución; en su defecto se usará un orden alfabético por nombre.
- **Segundo criterio:** Prioridad de estado según la sección 3.3.

### 3.3 Estados a Monitorear

| Prioridad | Estado          | Código |
|-----------|-----------------|--------|
| Máxima    | Hawái           | HI     |
| Máxima    | Colorado        | CO     |
| Adicional | Nuevo México    | NM     |
| Adicional | Misisipi        | MS     |
| Adicional | Nueva York      | NY     |
| Adicional | Florida         | FL     |
| Adicional | California      | CA     |
| Adicional | Delaware        | DE     |
| Adicional | Wyoming         | WY     |

Solo se verificarán corporaciones cuyo estado aparezca en esta tabla.

### 3.4 Proceso de Verificación por Corporación

1. Acceder al sitio web oficial de la Secretaría de Estado del estado correspondiente (ej. Hawaii Business Express, Colorado Secretary of State, etc.).
2. Localizar el registro de la corporación mediante búsqueda por nombre exacto o número de identificación si está disponible.
3. Extraer:
   - **Nombre del Presidente / Oficial principal**
   - **Nombre del Agente Registrado**
4. **Regla de detección de posible robo:**
   - El nombre del Presidente/Oficial **debe contener simultáneamente** “Marcio” **y** al menos uno de estos apellidos: “García”, “Andrade”.
   - Si **no** se cumple la condición → **Marcar como “Posible Robo”**.
5. Si se detecta un cambio (es decir, la corporación es marcada), generar una **captura en PDF del registro consultado** que sirva como evidencia.
6. Si la corporación está en estado **“Vendida”**, **omitir completamente** la verificación, sin importar lo que muestre el sitio de la Secretaría de Estado.

### 3.5 Reporte Diario (Excel/CSV)

Columnas obligatorias:

- `Nombre de la corporación`
- `Estado`
- `Nombres de los oficiales/agentes` (tal como aparecen en el sitio, separados por coma)
- `Estado del resultado`: “Limpio” o “Marcado”
- `Enlace al PDF` (si fue marcado), ruta en Dropbox/Google Drive
- `Fecha de verificación`
- `Notas` (opcional, por ejemplo “Posible robo”, “No se encontró registro”, “Error de acceso”, etc.)

El archivo se generará automáticamente al finalizar el escaneo diario y se guardará en la nube.

### 3.6 Almacenamiento en la Nube

- Los PDF y los reportes CSV se almacenarán en **Dropbox** o **Google Drive** (a elección del cliente).
- Estructura de carpetas: `YYYY-MM-DD/`
  - `reporte_YYYY-MM-DD.csv`
  - `pdfs/` → archivos `{NombreCorporacion}_{Estado}.pdf`

### 3.7 Notificación por Correo Electrónico

- Remitente configurable (SMTP, servicio externo como SendGrid).
- Destinatarios configurables.
- Asunto: `Alerta Diaria – Posibles Robos Corporativos – YYYY-MM-DD`
- Cuerpo: tabla resumen con las corporaciones marcadas (nombre, estado, oficiales/agentes, enlace al PDF). Si no hay marcadas, enviar un correo informando “Sin novedades”.

---

## 4. Requisitos Técnicos

- **Interfaz de usuario web** (panel de administración) que permita:
  - Visualizar el historial de escaneos diarios.
  - Revisar corporaciones marcadas, filtrar por fecha/estado.
  - Ver los PDF asociados.
  - Subir o actualizar el archivo CSV de entrada.
- **Backend** desarrollado en Flask, Django, Node.js o similar. Preferencia por Python por su ecosistema de scraping/IA.
- **Scraping**:
  - Capacidad de manejar múltiples sitios de Secretarías de Estado (cada uno con estructura diferente).
  - Gestión de **Captcha** y mecanismos anti‑bot: tiempos de espera aleatorios, pausas configurables, reintentos inteligentes (exponential backoff), uso de proxies si es necesario.
  - Motor de scraping con capacidad de ejecutar como tarea programada diaria (cron job, scheduler integrado o función serverless).
- **Manejo de la lógica de extracción con IA** (opcional, altamente deseable):
  - Uso de agentes LLM o modelos de lenguaje para normalizar nombres extraídos, detectar variaciones sospechosas (ej. “García” escrito como “Garcia” o “García”), y adaptarse a cambios en la estructura de los sitios web sin romper el parser.
  - Implementación que combine scraping determinista con fallback a IA para extraer datos cuando el parser falle.
- **Integración con API de Dropbox o Google Drive** para la escritura automática de archivos.
- **Almacenamiento seguro** de credenciales (variables de entorno, vault).
- **Diseño responsivo y seguro** (protección CSRF, autenticación de usuarios para el panel).

---

## 5. Reglas de Negocio Importantes

- **Exclusión por estado “Vendida”:** Cualquier corporación con esa condición en el archivo de entrada o en Salesforce **no debe ser verificada** bajo ninguna circunstancia. El sistema debe filtrarla antes de cualquier consulta a las Secretarías de Estado.
- **Condición de coincidencia de nombre:**  
  - Debe contener “Marcio” (ignorando mayúsculas/minúsculas).  
  - Debe contener “García” o “Andrade” (también case‑insensitive).  
  - Ambas condiciones deben ser verdaderas; basta con que falle una para marcar.
- **PDF de evidencia:** Solo se generará y almacenará si la corporación es marcada como “Posible Robo”. No se guardarán PDFs de verificaciones limpias para optimizar almacenamiento.

---

## 6. Aspectos de IA y Automatización (Opcional pero Preferente)

- **Normalización de nombres:** Uso de embeddings o expresiones regulares asistidas por LLM para igualar variantes tipográficas, inversiones de nombre/apellido, tildes, etc.
- **Detección de cambios estructurales en los sitios:** Un módulo de IA que compare la extracción actual con un patrón esperado y, si falla, active un proceso de re‑entrenamiento o ajuste manual asistido.
- **Clasificación de registros:** Agente que determine automáticamente si un registro es “Limpio” o “Marcado” con base en la regla de nombres, dejando trazabilidad de la decisión.

---

## 7. Cronograma Estimado (MVP)

- **Fase 1 – MVP HI + CO (Máxima prioridad):**  
  - Despliegue funcional que cubra los estados Hawái y Colorado.  
  - Carga de CSV, scraping específico para esos dos estados, detección de robo, generación de PDFs, reporte CSV diario y envío de correo.  
  - Almacenamiento en nube configurado.  
  - **Tiempo estimado:** 1–2 semanas desde el inicio.
- **Fase 2 – Expansión a los 7 estados adicionales:**  
  - Incorporación progresiva de los scrapers para NM, MS, NY, FL, CA, DE, WY.  
  - Mejoras de robustez y manejo de captchas.  
  - **Tiempo estimado adicional:** 1–2 semanas.

Se valorará positivamente la posibilidad de entregar un piloto funcional (HI+CO) en el menor tiempo posible.

---

## 8. Entregables del Proyecto

1. Código fuente completo, versionado en repositorio Git.
2. Documentación de instalación y despliegue (variables de entorno, dependencias, configuración de APIs de almacenamiento y correo).
3. Manual de usuario para el panel de administración.
4. Script de automatización diaria (cron, función serverless) o instrucciones para su programación.
5. Reporte de pruebas con ejemplos de corporaciones limpias y marcadas.

---

## 9. Información para Proveedores / Desarrolladores

Se solicita incluir en la propuesta:

- Cronograma detallado para el MVP (HI + CO) y para la versión completa.
- Enfoque técnico para el scraping de sitios estatales (manejo de Captcha, cambios de layout, extracción con IA).
- Estrategia de entrada de datos (CSV vs. API de Salesforce).
- Stack tecnológico propuesto (lenguaje, framework, bibliotecas para scraping, IA, almacenamiento, email).
- Experiencia previa con sitios de Secretarías de Estado o proyectos de scraping complejo.
- Portafolio / repositorios de GitHub relevantes.

---

## 10. Condiciones Comerciales

- **Compensación:** Tarifa fija de proyecto, con bono discrecional por entrega rápida y precisa.
- **Opcional:** Contrato de mantenimiento continuo post‑entrega (soporte, actualización de scrapers ante cambios en los sitios).

---

**Nota final:** Este proyecto es de máxima prioridad y con plazos ajustados. Solo se considerarán candidatos que puedan iniciar de inmediato y comprometerse a una entrega rápida del MVP funcional para Hawái y Colorado.