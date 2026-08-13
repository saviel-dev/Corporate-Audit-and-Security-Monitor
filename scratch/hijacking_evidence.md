# Evidencia de Secuestro Corporativo / Anomalías de Registro (Socrata)

## 1. Tabla de Variantes Deformadas (Ordenada por Fecha)

| Fecha Formación | Entity ID | Nombre de Entidad | Agente Registrado | Dirección del Agente |
|---|---|---|---|---|
| 2022-12-07 | 20228195975 | (Varias) | Marcio Garcio Andrade | 2236 E 109TH DR, NORTHGLENN, 80233 |
| 2022-12-16 | 20228222832 | (Varias) | Marcio Gracia | 2236 EAST 109TH DR, NORTHGLENN, 80233 |
| 2022-12-22 | 20228237745 | (Varias) | Marcio Garcio Garcia | 2236 E 109TH DRIVE, NORTHGLENN, 80233 |
| 2022-12-23 | 20228249820 | (Varias) | Marcio Andraded | 2236 E 109TH DRIVE, NORTHGLENN, 80233 |
| 2022-12-24 | 20228254204 | (Varias) | Marcio Garcia Adrade | 2236 EAST 109TH DRIVE, NORTHGLENN, 80233 |
| 2022-12-25 | 20228256990 | (Varias) | Marcio Garcio Andrade | 2236 E 109TH DRIVE, NORTHGLENN, 80233 |
| 2022-12-30 | 20228291095 | (Varias) | Marcio Garcio | 2236 E 109TH DR, NORTHGLENN, 80233 |
| 2023-04-23 | 20231428568 | (Varias) | MARCIO GRACIA ANDRADE | 2236 E 109TH DRIVE, NORTHGLENN, 80233 |
| 2023-04-24 | 20231433755 | Tegueste World LLC | MARCIO GARCIA ANDRRDE | 2236 E 109TH DRIVE, NORTHGLENN, 80233 |
| 2023-04-24 | 20231432884 | (Varias) | Marcio Garcia Adrade | 2236 E 109TH DRIVE, NORTHGLENN, 80233 |
| 2023-05-09 | 20231508044 | Alcott Sports LLC | Marcio Garcio | 2236 EAST 109TH DR, NORTHGLENN, 80233 |

> [!WARNING]
> **Coincidencia de Dirección:** El 100% de estas identidades deformadas comparten la **misma dirección física exacta** (2236 E 109th Dr, Northglenn, CO 80233) que los registros legítimos de "Marcio Garcia Andrade".

## 2. Análisis de Tiempos (Agrupación)
Las variantes no son erratas esporádicas distribuidas a lo largo de los años. Ocurrieron en dos ráfagas muy concentradas:
* **Ráfaga 1 (Diciembre 2022):** 7 registros anómalos creados en un lapso de 23 días.
* **Ráfaga 2 (Abril/Mayo 2023):** 4 registros creados en un lapso de 15 días.

## 3. Relevancia del Dataset (Marcio)
De los 15,000 registros analizados con el nombre "Marcio":
* **Registros vinculados al cliente** (Apellidos: Garcia, Andrade, Teixeira, Dias y sus deformaciones): **> 99%** de la muestra.
* **Personas ajenas** (Comparten "Marcio" pero distinto apellido/dirección): **< 1%** (Ej. *Marcio Nogueira, Marcio Caetano*).

## 4. Distancia de Levenshtein (Top Cercanos)
Tomando `Marcio Garcia Andrade` como objetivo principal (Longitud: 21):

| Nombre Registrado | Distancia | Notas |
|---|---|---|
| MARCIO GARCIA ANDRADE | 0 | Coincidencia exacta (dif. capitalización) |
| MARCIO GARCIA ANDRRDE | 1 | Substitución ('A' por 'R') |
| Marcio Garcia Adrade | 1 | Deleción ('n') |
| Marcio Garcio Andrade | 1 | Substitución ('a' por 'o') |
| MARCIO GRACIA ANDRADE | 2 | Transposición ('ar' por 'ra') |
| Marcio Andraded | 7 | Distancia alta (falta un apellido, sobra 'd') |
| Marcio Garcia | 8 | Distancia alta (falta un apellido) |
| Marcio Garcio Garcia | 9 | Substitución múltiple |

> [!IMPORTANT]
> Las deformaciones mantienen una distancia de Levenshtein muy baja (1-2), a excepción de las que omiten un apellido entero. Sin embargo, todas comparten la misma dirección postal. Esto requiere un cambio en la estrategia de detección (T-04).
