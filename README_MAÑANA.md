# README — Trabajo del martes (handoff al chat nuevo)

> **Para el asistente nuevo:** este archivo es el handoff de la sesión del 2026-05-17. Lee primero las secciones 1 y 2 para tener contexto. Luego ejecuta los pendientes de §3 en orden. **Antes de cualquier acción técnica, ejecuta el ítem 0 de advertencias críticas (revocar PAT).**

---

## 0. Advertencias críticas — LEER PRIMERO

- **Revocar el PAT clásico** `ghp_bLCG...sar7s` en https://github.com/settings/tokens. Quedó expuesto en la sesión anterior. Después de revocarlo, generar uno nuevo si hace falta y volver a configurar `git credential.helper store` en la laptop.
- **Sync de reloj Pi ↔ laptop es BLOQUEANTE**. Sin chrony funcionando, los CSVs del Pi (`resources.csv`) no se alinean con los de la laptop (`router.csv`, `backend_latency.csv`, `events.csv`) y el análisis cruzado queda inservible. Diagnóstico al inicio: `date` en laptop vs `ssh raspberry1@192.168.1.10 'date'` — si difieren > 1 s, instalar chrony antes de hacer cualquier otra cosa.
- **Regla CLAUDE.md**: un escenario a la vez en el Pi 3B+ (~900 MB RAM útiles). Apagar el anterior con `docker compose down` antes de levantar el siguiente.
- **Esc3 en demo pública**: NUNCA correr `loadgen.py`. Los alumnos generan el ataque desde sus teléfonos. Solo en lab.
- **Router OpenWrt**: nunca tocar la configuración vía LuCI cuando los flujos de Esc1 están activos — rompe los comandos SSH del dashboard. Usar solo Node-RED o SSH explícito.
- **Credenciales**: están en `~/tesis/metrics/.env` (gitignored) y CLAUDE.md. **NO repetirlas en commits ni en archivos versionados.**

---

## 1. Resumen de la sesión anterior (qué está hecho)

**Estado del prototipo al 2026-05-17:**

- **Marco teórico v4** ([tesis/esquema_marco_teorico_v4.md](../esquema_marco_teorico_v4.md)) cerrado: §1 fusionado, §3 aplanado, §2.4+§2.5 fusionados, §5 reorganizado (D3.js, tablas dinámicas HTML+Angular, diagrama esquemático Esc3, Flask como bullet en Python). §4 describe exactamente lo que se implementó en el harness.
- **Harness de métricas** completo en [tesis/metrics/](.):
  - `pi/collect_resources.py` (psutil+docker SDK con fallback cgroup v2)
  - `laptop/collect_router.py` (SSH al OpenWrt, `iw station dump`)
  - `laptop/loadgen.py` (asyncio ramp)
  - `flows_patch/metrics_middleware.js` (httpNodeMiddleware Node-RED)
  - `session.sh` (orquestador start/log/end)
  - `analyze.ipynb` (5 tablas + 5 plots PNG por escenario)
  - Validado end-to-end con Esc1 (212 muestras de recursos, 4408 latencias, 0 errores).
- **Encuesta**: form HTML configurable desde [survey/survey_template.json](survey/survey_template.json) (10 ítems: 6 SUS reducido + 2 pedagógicas + 2 texto libre), servida por Node-RED en cada escenario.
- **Los 3 escenarios desplegados en el Pi** (uno a la vez):
  - Esc1 :1881 (`esc1-nodered`)
  - Esc2 :1882 (`jp-esc2-nodered`)
  - Esc3 :1883 (`esc3-nodered`, `esc3-target`, `esc3-attacker`, `esc3-proxy`)
- **Esc3 tiene 4ta pestaña "04_ Encuesta"** con QR al estilo del primer QR (`.qr-dos-container`, rojo `#cc2222`/`#7f1d1d`, marco blanco, footer monospace). Texto: "ANTES DE IRTE" / "PASO FINAL // ENCUESTA DE SATISFACCIÓN".
- **GitHub repos**: `tesis_escenario1`, `tesis_escenario2`, `tesis_metrics`. **Falta**: crear remote para `tesis_escenario3` (solo local).
- **Documentación de campo**: [RUNBOOK_MIERCOLES.md](RUNBOOK_MIERCOLES.md) con pasos por escenario.

---

## 2. Decisiones tomadas en la sesión anterior

### 2.1 Encuesta única por componente (no por escenario)
La encuesta evalúa el **prototipo CEC-EPN como conjunto pedagógico**. Se entrega **una sola vez** al final del recorrido completo, en la 4ta tab de Esc3. Las preguntas hablan de los 3 escenarios juntos.

Redacción propuesta para los 10 ítems (a confirmar con el tutor antes de la demo):

| id | tipo | texto |
|---|---|---|
| sus1 | likert | "Los tres escenarios fueron fáciles de seguir." |
| sus2 | likert | "Necesité ayuda para entender qué hacer en cada escenario." (inverso) |
| sus3 | likert | "Los tres escenarios estuvieron bien integrados entre sí." |
| sus4 | likert | "Aprendí rápido qué estaba pasando en cada demostración." |
| sus5 | likert | "Me sentí cómodo participando con mi teléfono." |
| sus6 | likert | "Tendría que aprender mucho antes de usar algo así." (inverso) |
| ped1 | likert | "Comprendí los conceptos de ciberseguridad que se mostraron." |
| ped2 | likert | "Recomendaría estudiar Ingeniería en Tecnologías de la Información en la EPN." |
| mejoras | text | "¿Qué mejorarías del prototipo en conjunto?" |
| libre | text | "Algún comentario libre (escenario favorito, qué te sorprendió, etc.)" |

Los endpoints `/api/survey` de Esc1 y Esc2 quedan vivos como **fallback técnico**, pero los QR visibles dentro de los dashboards de Esc1/Esc2 se ocultan. Único QR público de encuesta: el de la 4ta tab de Esc3.

### 2.2 Consola operador en Node-RED en la laptop (no en el Pi)
- Por qué no en el Pi: el Pi 3B+ ya está saturado de RAM corriendo un escenario.
- Por qué Node-RED: coherente con la tesis, soporta `exec` nodes para SSH al Pi y al router, robusto bajo presión.
- **Modo dual**: pestaña "Demo" (wizard apto-para-tontos con 3 botones grandes "INICIAR DEMO ESC1/2/3" que hacen toda la secuencia atómica + botón rojo de pánico) + pestaña "Avanzado" (botones granulares por si algo falla).
- Implementación: contenedor Docker en la laptop puerto 1880, montando `~/tesis/metrics` como volumen.

### 2.3 Ensayo en casa antes del miércoles
4 dispositivos (3 teléfonos + 1 tablet), las 3 demos completas, encuesta única al final de Esc3, mismo cableado que el aula.

### 2.4 PDF entregable con pandoc + LaTeX
`report_consolidado.md` → `reporte.pdf` con plantilla eisvogel, incluye portada, glosario de métricas y secciones por escenario.

### 2.5 Métricas faltantes a agregar (críticas)
El harness actual cubre las 4 familias del plan F_AA_234A, pero hay datos pedagógicamente centrales que NO están en CSV. Ver §4 para detalle.

---

## 3. Pendientes para mañana (orden ejecutable)

| # | Tarea | Tiempo | Bloqueante |
|---|---|---|---|
| 1 | **Sincronizar reloj Pi ↔ laptop** (instalar chrony, configurar Pi como cliente, agregar check en `session.sh start` que aborte si offset > 2 s) | 30 min | **SÍ — sin esto el análisis cruzado no sirve** |
| 2 | Reescribir [survey/survey_template.json](survey/survey_template.json) con los 10 ítems del prototipo en conjunto (§2.1) | 10 min | No |
| 3 | Ocultar QR de encuesta en Esc1/Esc2 (patch a `flows.json` vía Admin API, no edición manual) | 15 min | No |
| 4 | Agregar `GET /api/export_state` en los 3 Node-RED para exportar tablas del dashboard a CSV — Esc1 auditoría, Esc2 capturas/clicks/envíos, Esc3 stats snapshots | 45 min | No (reducible si falta tiempo) |
| 5 | Crear `laptop/target_health_probe.py` — probe HTTP cada 1 s al target Flask de Esc3, registra fase IDLE/ATAQUE/PROTEGIDO | 30 min | No (reducible si falta tiempo) |
| 6 | Capturar `docker events` durante la sesión y consolidar en `events.csv` | 20 min | No (reducible si falta tiempo) |
| 7 | Levantar consola Node-RED operador en la laptop (modo wizard + experto) | 2.5 h | Recomendado |
| 8 | Ampliar `analyze.ipynb`: §4.4 + 2 plots faltantes (disponibilidad + RX/TX) + 3 plots nuevos (target_health Esc3, funnel Esc2, adopción Esc1) + reporte consolidado + glosario + análisis estadístico | 2 h | Recomendado |
| 9 | Pipeline pandoc → PDF con plantilla eisvogel | 30 min | Recomendado |
| 10 | **Ensayo en casa con 4 dispositivos**, las 3 demos completas | ~2 h | **SÍ** |
| 11 | Generar `reporte.pdf` del ensayo como prueba end-to-end | 10 min | Recomendado |
| 12 | Actualizar [RUNBOOK_MIERCOLES.md](RUNBOOK_MIERCOLES.md) según lo aprendido en el ensayo | 30 min | Recomendado |

**Total**: ~9 h efectivas. Si se pasa de tiempo, los ítems 4-6 son los más reducibles; el resto es bloqueante para la demo del miércoles.

---

## 4. Métricas a agregar y por qué

### 4.1 Esc3 — `target_health.csv` (disponibilidad del target Flask)
El middleware actual instrumenta el Node-RED **orquestador**, no el target. La métrica que ilustra el escenario DoS es exactamente la del target: cuánto cae durante ATACAR, cuánto se recupera con PROTEGER.

- Probe HTTP cada 1 s desde la laptop: `GET http://192.168.1.10:5000/`
- Columnas: `ts, status_code, response_ms, phase` (phase = idle | ataque | protegido)
- Análisis: ventanas pre/durante/post ATACAR, comparar disponibilidad y p95.

### 4.2 Tablas del dashboard → CSV (Esc1, Esc2, Esc3)
Las tablas que ya se muestran en los dashboards son data crítica que solo vive en memoria de Node-RED. Hay que cosecharla.

- **Estrategia general**: cada Node-RED expone `GET /api/export_state` que devuelve JSON con la data subyacente. `session.sh end` lo llama y lo persiste como CSV.
- **Esc1**: `auditoria_usuarios.csv` (la tabla de usuarios detectados).
- **Esc2**: `email_capturas.csv`, `email_envios.csv`, `email_clicks.csv` (las 3 tablas del dashboard).
- **Esc3**: `esc3_stats_snapshot.csv` (snapshots cada 5 s de RPS, % protección, contador de ataques).

### 4.3 `docker_events.log` (restarts / OOM kills)
Si un contenedor se cae u OOM-kill durante la demo (riesgo real en Pi 3B+), hoy no queda evidencia. Capturar `docker events` en background durante la sesión y agregarlo a `events.csv` como `event=container_<action>`.

**Cobertura tras estos cambios**: el harness pasa de "las 4 familias obligatorias del plan" a capturar **toda la evidencia que las demos están generando en pantalla**.

---

## 5. Glosario de métricas (incluir en el PDF)

| Métrica | Qué mide | Unidad | Por qué importa |
|---|---|---|---|
| **p50 (mediana)** | El 50% de las peticiones se completó en este tiempo o menos. | ms | Caso típico de respuesta. |
| **p95** | El 95% de las peticiones se completó en este tiempo o menos. | ms | Peores casos comunes (1 de cada 20). Indicador estándar de SLA. |
| **p99** | El 99% de las peticiones se completó en este tiempo o menos. | ms | Colas largas (1 de cada 100). Picos de degradación. |
| **RPS** | Peticiones HTTP por segundo procesadas por el servidor. | req/s | Capacidad de trabajo. |
| **Knee de concurrencia** | Primer nivel de concurrencia donde latencia o errores se disparan. | concurrencia (int) | Techo práctico del servidor. |
| **Disponibilidad** | % de peticiones con respuesta HTTP 2xx sobre el total. | % | Confiabilidad del servicio durante la demo. |
| **SUS score** | System Usability Scale (Brooke 1996), reducido a 6 ítems (Lewis & Sauro 2017). | 0–100 | >68 = "por encima del promedio" en estudios estandarizados. |
| **NPS pedagógico** | Net Promoter Score adaptado: % "promotores" (recomiendan la carrera) − % "detractores". | -100 a +100 | Intención de recomendación. Métrica directa del objetivo pedagógico. |
| **CPU %** | % de uso de CPU promediado sobre todos los cores del Pi. | % (0-100) | Sostenido >80% = dispositivo saturado. |
| **RAM MB** | Memoria RAM en uso (RSS). | MB | El Pi 3B+ tiene ~900 MB útiles. Cerca del límite = OOM. |
| **Click-through rate** | % de los que dieron email y luego clickearon el enlace educativo. | % | Efectividad pedagógica de Esc2. |
| **Asociaciones WiFi** | Dispositivos conectados al SSID del público en un instante. | dispositivos | Concurrencia real, contrapuesta a la sintética del loadgen. |

---

## 6. Ideas para la sección "Análisis de resultados" de la tesis

Con la data rica que vamos a tener, vale la pena estructurar el análisis para que el capítulo no sea "tablas y gráficos sueltos".

### Por escenario

**Esc1 — análisis pasivo de red:**
- Curva de adopción: # dispositivos descubiertos vs tiempo (S-curve esperada).
- Correlación: # dispositivos vs CPU del Pi (scatter + r²). Cuantifica si nmap escala o satura.
- Distribución de tipos de dispositivo si la auditoría lo captura.

**Esc2 — phishing:**
- **Funnel de conversión** (métrica clave): visita → email entregado → click al enlace → vista educativa. Tasa de cada paso.
- Distribución temporal de captura de emails (picos al QR vs picos post-explicación).
- Categorización de dominios de email (gmail/hotmail/EPN), anonimizando.

**Esc3 — DoS:**
- **Ventana antes / durante / después** (métrica clave): 30 s pre-ATACAR, durante ATACAR, 30 s post-PROTEGER. Comparar disponibilidad, RPS, p95.
- Efecto de la protección: delta de disponibilidad entre ATACAR sin proxy y ATACAR con proxy.
- Recovery time: segundos hasta recuperar 95% disponibilidad tras activar PROTEGER.

### Cross-escenario (sección consolidada)
- Comparativa de carga: cuál escenario fue más exigente para el Pi (CPU/RAM peak).
- Comparativa de respuesta: cuál escenario tuvo mejor p95 backend.
- SUS unificado vs ítems: identificar dimensiones percibidas mejor/peor.
- Sentiment simple en textos libres: word cloud + frecuencia.
- **NPS pedagógico global**: ¿cuántos recomendarían la carrera? Es la métrica de impacto pedagógico.

### Análisis estadístico mínimo (para defender ante el jurado)
- Intervalos de confianza al 95% en SUS (n probablemente < 30, usar t-Student).
- Test de Wilcoxon antes/durante/después en Esc3 (no asume normalidad).
- Reportar n explícitamente en cada tabla.

---

## 7. Archivos críticos a modificar / crear

**Modificar:**
- [survey/survey_template.json](survey/survey_template.json)
- `flows.json` de Esc1/Esc2/Esc3 (vía Admin API, no edición manual)
- [analyze.ipynb](analyze.ipynb)
- [session.sh](session.sh)
- [RUNBOOK_MIERCOLES.md](RUNBOOK_MIERCOLES.md)

**Crear:**
- `ops-console/` (flows.json del operador wizard+experto, docker-compose.yml, README.md)
- `laptop/target_health_probe.py`
- `templates/eisvogel.tex` (plantilla Pandoc)
- `report_consolidado.md` (generado por el notebook)
- `reporte.pdf` (generado por pandoc)
- Configuración chrony en laptop + cliente NTP en Pi

---

## 8. Verificación end-to-end al cierre del día

- [ ] Reloj Pi y laptop con drift < 1 s.
- [ ] 3 carpetas en `sessions/` del ensayo, cada una con sus CSVs llenos.
- [ ] `survey.csv` (solo en sesión de Esc3) con ≥ 4 filas reales.
- [ ] `target_health.csv` (Esc3) muestra las 3 fases.
- [ ] Notebook genera `report_consolidado.md` sin errores.
- [ ] `reporte.pdf` se genera y es legible.
- [ ] Consola operador responde a los 3 botones "INICIAR DEMO".
- [ ] RUNBOOK actualizado con cualquier hallazgo del ensayo.
- [ ] PAT clásico revocado en GitHub.
