# Explicación de las métricas del prototipo

> Documento en lenguaje sencillo para explicar al tutor **qué medimos, cómo, con qué
> herramientas y por qué lo hacemos así**. Complementa a `METRICAS.md` (que es la
> auditoría técnica del harness). Aquí el enfoque es explicativo, no de implementación.

## Introducción: tres capas de medición

El prototipo se mide en tres capas, que responden a preguntas distintas:

| Capa | Qué tipo de dato mide | Pregunta que responde |
|---|---|---|
| **Router** | Hardware (CPU, memoria, red) + equipos conectados | ¿La red aguanta? ¿Quién está conectado? |
| **Raspberry Pi** | Hardware (CPU, memoria, red) del servidor y de cada contenedor | ¿El servidor aguanta la jornada? |
| **Escenarios** | Comportamiento de la aplicación | ¿El servicio responde, cuánto tarda, a cuántos afecta? |

Las dos primeras miden **hardware**; la tercera mide **comportamiento**. Cruzando ambas
en la misma línea de tiempo se obtiene el argumento más fuerte: *por ejemplo, ver que en
el segundo en que el servidor dejó de responder, el procesador de la Pi estaba al 100 %*.

Esto se alinea con el **§1.4.4 del marco teórico**, que define cuatro métricas de
evaluación del prototipo:

| Métrica del marco (§1.4.4) | Dónde se cubre en este documento |
|---|---|
| §1.4.4.1 Satisfacción de la audiencia | Encuesta (global, no por escenario) |
| §1.4.4.2 Desempeño funcional (latencia, concurrencia, disponibilidad) | Escenarios + concurrencia en el router |
| §1.4.4.3 Consumo de recursos en hardware de borde | Router + Pi |
| §1.4.4.4 Tiempos de montaje y despliegue | Escenarios (despliegue) + cronómetro (montaje) |

### Por qué no usamos `top` ni `ntop` (aplica a todo)

- **`top`** solo *muestra* el consumo en pantalla en el momento; **no guarda historial**.
  La tesis necesita la evolución en el tiempo para graficarla, y eso `top` no lo deja.
- **`ntop`/`ntopng`** habría que *instalarlo y dejarlo corriendo* con su propia base de
  datos; es pesado, y en un equipo de borde **la herramienta de medir consumiría más
  recursos que lo que se quiere medir**.
- Solución: leemos la **misma fuente de datos** que esas herramientas usan por dentro
  (los archivos del sistema Linux) y la guardamos nosotros en CSV.

---

## 1. Métricas del ROUTER (OpenWrt)

### ¿Qué medimos?
- **Procesador y memoria** del router mientras trabaja.
- **Tráfico de red**: datos que entran y salen por WiFi y por cable (LAN).
- **Equipos conectados**: cuántos hay y, uno por uno, su dirección, nombre, señal y consumo.

### ¿Cómo lo medimos?
El router tiene Linux, que guarda el estado del sistema en "archivos espejo" que se
actualizan solos. Solo los **leemos** y hacemos la cuenta:
- Procesador → del archivo que cuenta el tiempo ocupado vs. libre del CPU.
- Memoria → del archivo que reporta RAM total y disponible.
- Tráfico → de los contadores de bytes por interfaz (restando dos lecturas → velocidad).
- Equipos → del comando que lista los conectados al WiFi, cruzado con la "guía" del
  router que asocia cada equipo con su nombre y dirección (leases DHCP).

**No se instala nada en el router**: todo eso ya viene en él.

### ¿Con qué herramienta?
Un programa propio en **Python que corre dentro de la Raspberry Pi** (`collectors/collect_router.py`),
que se conecta al router por **SSH**, lee los datos, hace los cálculos en la Pi y los
guarda en CSV. **La laptop no interviene en la medición**: solo dispara la sesión por SSH y,
al final, descarga los CSV para graficarlos.

### ¿Por qué NO se procesa ni se guarda dentro del router?
Porque el router es el equipo más chico y su único trabajo crítico es **mantener
conectada a las 20+ personas sin caerse**. Ponerlo a guardar y clasificar le quitaría
recursos justo en el peor momento (más aún durante el escenario de ataque). Tres razones
concretas, verificadas en el equipo:
- **No tiene dónde guardar seguro**: el único espacio libre vive en la RAM (~73 MB libres)
  y **se borra al reiniciar**; la memoria fija es de solo ~8 MB y escribir cada pocos
  segundos la desgasta.
- **No tiene Python** ni herramientas de análisis para clasificar ahí.
- **El cálculo es trivial para la Pi** pero costoso para un router diminuto.

División de tareas: el router solo **entrega** sus datos en crudo; la Pi **calcula y
guarda**. (La Pi y el router están en la misma red LAN, así que la Pi llega al router por
SSH igual que antes lo hacía la laptop, sin pasar por internet.)

### Archivos que se generan
| Archivo | Contenido |
|---|---|
| `router_resources.csv` | CPU y memoria del router |
| `router.csv` | Tráfico WiFi/LAN, nº de equipos conectados, leases DHCP activas |
| `router_devices.csv` | Un equipo por fila: MAC, IP, nombre, señal, consumo |

### Flujo
Cada **5 segundos** la Pi entra por SSH al router, lee los datos, calcula y agrega
una fila a esos CSV — todo guardado en la Pi. No se instala ni se guarda nada en el router,
y la laptop no participa.

---

## 2. Métricas de la RASPBERRY PI

### ¿Qué medimos?
- **Procesador, memoria y red de la Pi** (el equipo completo) mientras sirve el escenario.
- **Lo mismo, pero de cada contenedor por separado**: el panel de control, el servidor
  atacado, el atacante y el proxy de protección, cada uno por su lado.

### ¿Cómo lo medimos?
A diferencia del router, **la Pi sí se mide a sí misma desde adentro**, porque es una
computadora completa con memoria y espacio de sobra. Un programa propio corre *dentro* de
la Pi y, **cada segundo**:
- Pregunta al sistema cuánto procesador y memoria usa y cuántos datos pasaron por la red.
- Le pide a Docker el consumo de cada contenedor.
- Anota una fila por segundo: una para la Pi y una por cada contenedor.

### ¿Con qué herramienta?
Un programa propio en **Python que corre dentro de la Pi** (`pi/collect_resources.py`),
apoyado en la librería **`psutil`** (lee CPU, memoria y red; misma fuente que usa `top`,
pero entregando los números listos para guardar) y en la información del propio **Docker**.

### ¿Por qué aquí SÍ se mide "desde adentro" y en el router no?
Porque la Pi **tiene con qué**: es el servidor principal, con memoria y disco suficientes
para correr el medidor sin afectarse. El router es un equipo diminuto cuyo único trabajo es
dar internet, y no le sobran recursos.
- La Pi se mide **a sí misma** (programa local).
- El router se mide **desde la Pi** (la Pi lee sus datos por SSH; antes lo hacía la laptop).

### El recurso crítico: la memoria
La Pi tiene **~1 GB de RAM**. Por eso **no se corren los tres escenarios al mismo tiempo**:
se presenta uno a la vez. Esta métrica de consumo es la que **sustenta esa decisión de
diseño** y prueba que el prototipo es viable en hardware portátil. El §1.4.4.3 del marco lo
dice explícito: *la memoria es el recurso que define la arquitectura del prototipo*.

### Archivo que se genera
| Archivo | Contenido |
|---|---|
| `resources.csv` | Una fila por segundo: CPU, memoria y red de la Pi y de cada contenedor |

### Flujo
El orquestador, que **corre en la Pi**, arranca el medidor localmente. La Pi escribe su
archivo *localmente*, segundo a segundo, junto a los del router y los escenarios (todos con
el reloj de la Pi). Al cerrar la sesión, la laptop **descarga toda la carpeta** para graficarla.

---

## 3. Métricas de los ESCENARIOS

Mientras el router y la Pi miden el *hardware*, los escenarios miden el *comportamiento*:
si el servicio responde, cuánto tarda y cuál fue el resultado de la demostración.

### ¿Qué medimos?
| Qué medimos | Escenario | Para qué sirve |
|---|---|---|
| **Disponibilidad del servidor atacado** (responde o no, y en qué fase: normal / ataque / protegido) | Esc3 (DoS) | Métrica estrella: muestra la caída con el ataque y la recuperación al activar la protección |
| **Latencia del backend** (cuánto tarda el servidor en responder) | Los 3 | Se mide *en el servidor*, no en el WiFi ni en el navegador del visitante |
| **Tiempo de despliegue** (cuánto tarda en levantarse el escenario) | Los 3 | Demuestra arranque rápido y reproducible |
| **Datos propios del escenario** (correos capturados, clics, dispositivos, DNS, estadísticas del ataque) | Cada uno los suyos | Resultado pedagógico de la demostración |
| **Eventos de los contenedores** (si una caja se reinicia, muere o se queda sin memoria) | Los 3 | Deja rastro si algo se cae durante la demo |

> Aclaraciones de nivel: la **concurrencia real** (cuántos teléfonos a la vez) se mide en el
> **router**, no en el escenario. Y la **satisfacción de la audiencia** (encuesta) es una
> métrica **global del prototipo**, se toma una sola vez al final del Esc3 — no es por escenario.

### ¿Cómo lo medimos?
- **Disponibilidad** → un "sondeo": cada segundo se hace una petición al servidor y se anota
  si respondió, cuánto tardó y en qué fase estaba.
- **Latencia** → el propio panel Node-RED se cronometra a sí mismo en cada petición.
- **Despliegue** → se levanta el escenario desde cero y se cronometra hasta la primera respuesta.
- **Datos propios** → el panel ya lleva esas tablas por dentro; al cerrar la sesión se le
  piden y se vuelcan a archivos.
- **Eventos** → se "escucha" al sistema que ejecuta las cajas y se anota cada arranque, parada o caída.

### ¿Con qué herramientas?
- Programas propios en **Python que corren dentro de la Pi** (`collectors/`): sondeo de
  disponibilidad (`target_health_probe.py`), cronómetro de despliegue (`measure_deploy.py`),
  registrador de eventos (`docker_events_collector.py`).
- Un **complemento dentro de Node-RED** (`flows_patch/metrics_middleware.js`) para la latencia.
- Las tablas internas del panel se descargan con `fetch_export_state.py`.
- Todo liviano, **sin instalar nada pesado**: peticiones HTTP normales y consultas al sistema.

### ¿Cómo se integra?
El orquestador `session.sh`, que **corre en la Pi**, lanza estos medidores junto con los del
router y la propia Pi, **todos a la vez y con la misma marca de tiempo** (un solo reloj, el de
la Pi). Así las tres capas quedan en la misma carpeta de sesión y se pueden cruzar. La laptop
solo dispara `session.sh` por SSH (con `gateway/session.ps1`) y descarga la carpeta al final.

### Archivos que se generan
| Archivo | Contenido | Cuándo se obtiene |
|---|---|---|
| `target_health.csv` | Disponibilidad del servidor (Esc3) | En vivo, en la Pi |
| `docker_events.csv` | Eventos de contenedores | En vivo, en la Pi |
| `deploy.csv` | Tiempo de despliegue | En vivo, en la Pi |
| `backend_latency.csv` | Latencia del backend | Escrito en la Pi, descargado al cerrar |
| `dns_queries.csv` | Consultas DNS de uso activo (Esc1) | Escrito en la Pi, descargado al cerrar |
| `email_capturas.csv`, `email_clicks.csv` | Phishing (Esc2) | Tablas del panel (`/api/export_state`) |
| `esc3_stats_snapshot.csv` | Estadísticas del ataque (Esc3) | Tablas del panel (`/api/export_state`) |
| `auditoria_usuarios.csv` | Dispositivos detectados (Esc1) | Tablas del panel (`/api/export_state`) |

### Métricas frágiles (qué podría no funcionar o no valer en la demo)

**La más frágil — detección de dispositivos y DNS del Esc1.** Es la que más probablemente
quede **subestimada** en una demo real, y por una limitación de fondo, no por un bug:
- Los teléfonos con **DNS cifrado** (DoH / DNS privado / AdGuard) no envían sus consultas
  al router, así que **esos equipos no aparecen** en el mapa ni en la tabla de dominios.
- La **aleatorización de MAC** hace que el fabricante salga "Desconocido" (se infiere del
  hostname como parche).
- Con **más de 20 usuarios** el grafo se pone lento.
- Consecuencia: el criterio de "≥95 % de dispositivos detectados" puede no cumplirse por el
  DoH, no por fallo del sistema. **Presentarlo como alcance metodológico.**

**Otras de menor riesgo, ya controladas:**
| Métrica | Riesgo | Mitigación |
|---|---|---|
| Tablas de dominio (correos, ataque, auditoría) | Si se usa `presentation.sh` en vez de `session.sh`, no se captura nada (ya pasó el 20-may) | Usar siempre `session.sh` |
| Latencia del backend | Si el middleware no está activo en ese escenario, el CSV sale vacío | Verificar antes de la demo |
| Disponibilidad del Esc3 | El "caído" visual es animación, desacoplado de la salud real | Reportar `target_health.csv`; el operador dispara el flood real |
| Concurrencia real | Si el nombre de la interfaz WiFi está mal configurado, cuenta 0 equipos | Confirmar `wifi_iface` correcto |
| Encuesta | Depende del endpoint `/api/survey` y de que el público la conteste | Verificar endpoint; asumir respuesta parcial |
| Sincronía de reloj entre CSV | Ya no es un riesgo: todos los colectores corren en la Pi y comparten su reloj | — (antes había que sincronizar Pi↔laptop con `chrony`) |

---

## 4. Avisos de exactitud (verificados por SSH)

Desfases entre el documento de tesis y lo que está corriendo hoy, a corregir antes de la entrega:
- El PDF (§2.1) dice **OpenWrt 22.03**, pero el router corre **OpenWrt 24.10.4**.
- El PDF dice **Raspbian Bookworm / Pi 3B+ 1 GB**; la RAM reportada (~906 MB) es consistente
  con 1 GB, pero conviene **confirmar la versión exacta del SO** de la Pi.

---

## 5. Pendiente de verificación (próxima sesión)

> El equipo (Pi y router) quedó **desconectado**, así que estas dos comprobaciones —que
> dependen de tener el escenario desplegado y accesible por SSH— **no se pudieron hacer** y
> quedan para una próxima sesión con todo encendido.

1. **Middleware de latencia activo** — confirmar que `flows_patch/metrics_middleware.js`
   está enganchado en el `settings.js` del escenario y que, al recibir peticiones, escribe
   filas en `backend_latency.csv`. Si no está, esa métrica saldría vacía.
2. **Endpoint `/api/survey` desplegado (Esc3)** — confirmar que el flow del Esc3 en la Pi
   tiene el endpoint que recibe la encuesta y agrega filas a `survey.csv`. Verificar en una
   corrida real de Esc3 que la fila efectivamente se escribe.

Cómo verificar cuando el equipo esté encendido (referencia):
- Levantar el Esc3 en la Pi y abrir una sesión con `session.sh start esc3`.
- Enviar una respuesta de prueba a la encuesta y una petición cualquiera al panel.
- Cerrar con `session.sh end` y revisar que `backend_latency.csv` y `survey.csv` tengan filas.

---

## Resumen en una frase

> Medimos las tres capas (router, Pi y escenarios) leyendo los datos que el sistema Linux ya
> tiene y guardándolos en CSV con un solo reloj (el de la Pi); no usamos `top`/`ntop` porque no
> guardan historial o son demasiado pesados; **toda la recolección corre en la Pi** (el router se
> mide por SSH desde la Pi, no desde la laptop, para no robarle recursos al router; la Pi se mide a
> sí misma porque tiene capacidad). **La laptop solo dispara la sesión y descarga los CSV para
> graficar.** La única métrica a presentar con matices es la detección DNS del Esc1, porque los
> teléfonos con DNS cifrado no pasan por el router.
