# notas.md — Reglas del proyecto Corp Monitor

Este archivo es la fuente de verdad de las reglas de trabajo del agente.
Debe leerse **antes de cualquier acción** cuando se toma el relevo de otro modelo.

---

## 1. Reglas duras (no negociables)

Estas reglas se cumplen siempre, sin excepción, incluso si se piden
explícitamente durante una tarea.

### 1.1 Control de versiones

- **Prohibido ejecutar `git commit`, `git push`, `git merge`, `git rebase`,
  `git reset --hard` o cualquier comando que altere el historial o el remoto.**
- Prohibido crear ramas, tags, Pull Requests o releases.
- Prohibido modificar `.git/`, hooks de git o la configuración del repositorio.
- Puedes usar comandos de solo lectura: `git status`, `git diff`, `git log`, `git show`.
- Si una tarea parece requerir un commit, **detente y avisa**. Describe los
  cambios en texto y deja que el usuario decida.
- Al terminar una tarea, incluye un resumen de archivos modificados/creados y,
  si se quiere, un mensaje de commit **sugerido** en texto plano. Nunca lo ejecutes.

### 1.2 Alcance de los cambios

- No modifiques archivos fuera del alcance de la tarea pedida.
- No borres archivos ni migraciones existentes sin preguntar antes.
- No ejecutes migraciones destructivas (`flush`, `--fake`, borrado de tablas)
  sin confirmación explícita.

### 1.3 Base de datos de producción

- **Prohibido ejecutar `INSERT`, `UPDATE`, `DELETE`, `DROP` o `ALTER` contra
  la base de producción (Neon / `DATABASE_URL`). `SELECT` sí está permitido.**
- Las pruebas que requieran modificar datos van contra SQLite local o una base
  de desarrollo separada. Si no existe, pedirla antes de improvisar.
- Ningún script de prueba debe leer `DATABASE_URL`. Deben apuntar
  explícitamente a la base local (ej. `sqlite:///instance/monitor_dev.db`).
- Si una tarea parece exigir escribir en producción, **detente y pregunta**.
- Antes de cualquier escritura en producción autorizada, ejecutar un volcado
  completo con `pg_dump` y confirmar ruta y tamaño del archivo resultante
  (regla D-05).

---

## 2. Diseño e interfaz (flat design)

### 2.1 Principios visuales

- Estilo **flat design**: paleta de colores sólidos, sin gradientes, sin
  sombras difusas, sin texturas, sin efectos 3D o skeuomórficos.
- Paleta limitada: 1 color primario, 1 secundario, 1 de acento y una escala
  de neutros. Define todo con variables CSS (`:root { --color-primary: ... }`)
  y **nunca** escribas colores hardcodeados en los componentes.
- Espaciado y tipografía consistentes mediante una escala definida.
- Bordes: radios pequeños y uniformes o esquinas rectas. Elige una opción y
  mantenla en todo el proyecto.

### 2.2 Botones

Un botón **no debe distinguirse únicamente por su color de relleno**.
Cada botón debe combinar el color sólido con al menos dos refuerzos visuales:
- Borde definido (`border: 2px solid`) o estilo *outline* para acciones secundarias.
- Jerarquía clara: primario (relleno sólido + borde), secundario (solo borde),
  terciario (solo texto).
- Estados diferenciados y visibles: `:hover`, `:focus-visible`, `:active`,
  `:disabled`.

Nunca uses el color como único portador de significado.

### 2.3 Implementación

- CSS en archivos propios dentro de `static/css/`. Nada de estilos inline.
- Nomenclatura de clases consistente (BEM o utilidades). No mezcles convenciones.
- HTML semántico y accesible: labels asociados, `aria-*` donde haga falta,
  navegación por teclado funcional.
- Diseño responsive con mobile-first.

---

## 3. Calidad del código

### 3.1 Python / Flask

- Sigue **PEP 8**. Type hints en funciones y métodos públicos.
- **Todo el código se escribe en español** (ver sección 3.2).
- Funciones cortas y con una sola responsabilidad.
- Lógica de negocio en `services/` o `scrapers/`, no en `routes.py`.
- Usa el ORM (SQLAlchemy). Sin SQL crudo salvo justificación.
- Valida siempre los datos de entrada del usuario.
- Nada de secretos en el código: usa variables de entorno (`.env`).
- Prohibido dejar código muerto, `print()` de depuración o `TODO` sin ticket.

### 3.2 Idioma del código (español)

Todo lo que escribamos nosotros va en **español**: nombres de variables,
funciones, clases, modelos, atributos, módulos, archivos, mensajes de error,
docstrings y comentarios.

- Sin tildes ni `ñ` en identificadores.
- `snake_case` para variables, funciones y módulos.
- `PascalCase` para clases. `MAYUSCULAS` para constantes.
- Los **valores de datos** que espejean sistemas externos (como `status`)
  se mantienen en el idioma de ese sistema (ver D-02 en `decisiones.md`).

### 3.3 Comentarios (solo donde aportan)

- No comentes lo obvio.
- Comenta únicamente el **porqué** de decisiones no evidentes, algoritmos
  complejos o reglas de negocio de origen externo.
- Usa docstrings estilo Google en modelos, servicios y funciones públicas.

---

## 4. Estructura y organización

- La aplicación sigue una estructura modular Flask con carpetas:
  `app/scrapers/`, `app/services/`, `app/static/`, `app/templates/`.
- Nuevos archivos y carpetas en español (salvo estándar del ecosistema).
- Si un archivo supera ~300 líneas, dividir en módulos coherentes.
- **Antes de crear algo nuevo:** verificar si ya existe un módulo que lo resuelva.

---

## 5. Flujo de trabajo esperado

1. **Analiza** el código existente relacionado antes de escribir.
2. **Lee** `notas.md`, `docs/task.md` y `docs/decisiones.md` al tomar el relevo.
3. **Propón un plan** breve si la tarea toca más de dos archivos o implica
   migraciones.
4. **Implementa** de forma incremental, un cambio coherente a la vez.
5. **Verifica**: ejecuta los tests y el linter cuando existan.
6. **Reporta**: lista los archivos tocados y el mensaje de commit sugerido —
   sin ejecutarlo.

Si algo del requisito es ambiguo, **pregunta antes de asumir**.

---

## 6. Reglas de datos y pruebas

- **NUNCA inventes datos de prueba.** Si necesitas nombres de corporaciones,
  consúltalos en la BD o en el portal público. Si no los consigues, di claramente
  que no puedes avanzar sin ellos.
- No declares una tarea cerrada sin evidencia ejecutada. "Debería funcionar"
  y "el selector es correcto" no son evidencia; la salida cruda sí.
- Los scripts de prueba aislados van en `scratch/` con nombre descriptivo.
  Nunca se eliminan sin avisar al usuario.

### 1.4 Regla de oro para Playwright
Prohibido instanciar Playwright directamente fuera de app/scrapers/base.py. Todo scraping, incluidas pruebas y scripts de diagn�stico, pasa por el flujo de base.py (o su funci�n run_diagnostic), que garantiza stealth y pausas. Un script que llame a sync_playwright() por su cuenta es un bug, no un atajo.
