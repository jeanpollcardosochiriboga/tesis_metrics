# Instalación del middleware de latencia en Node-RED

El middleware `metrics_middleware.js` registra en `backend_latency.csv` una línea
por cada petición HTTP atendida por Node-RED — sin tocar `flows.json`.

## Pasos (por escenario, una vez)

1. **Copiar el middleware al repo del escenario** (ej. Esc1):
   ```bash
   cp tesis/metrics/flows_patch/metrics_middleware.js \
      Escritorio/tesis_escenario1/metrics_middleware.js
   ```

2. **Editar `settings.js`** del escenario, agregar dos líneas:

   Cerca del inicio (después de los `require` existentes, si los hay):
   ```js
   const metricsMW = require('./metrics_middleware');
   ```

   Dentro de `module.exports = { ... }`, agregar la propiedad
   `httpNodeMiddleware`. Si la propiedad ya existe (está comentada en el
   template default), descomentarla y reemplazar el cuerpo:
   ```js
   httpNodeMiddleware: metricsMW,
   ```

3. **Reiniciar el contenedor** para que Node-RED relea `settings.js`:
   ```bash
   cd Escritorio/tesis_escenario1
   docker-compose restart
   ```

4. **Verificar**: tras una petición al dashboard, debe existir
   `metrics_out/backend_latency.csv` en el repo (montado en `/data/metrics_out`
   dentro del contenedor):
   ```bash
   tail -5 metrics_out/backend_latency.csv
   ```

## Salida

`metrics_out/backend_latency.csv` (gitignored), columnas:

| Columna | Descripción |
|---|---|
| `ts` | Epoch float en segundos cuando se recibió la petición |
| `endpoint` | URL path (incluye query string) |
| `method` | GET, POST, etc. |
| `processing_ms` | Tiempo entre request received y response finished |
| `status_code` | HTTP status |

El orquestador `session.sh end` mueve este archivo a `sessions/<id>/` al cerrar
la sesión, dejando el original vacío para la siguiente.

## Nota sobre rendimiento

El middleware usa `fs.appendFile` (asíncrono) y `process.hrtime.bigint()` para
medir con resolución de nanosegundos. El overhead por petición es de orden de
microsegundos — despreciable comparado con cualquier procesamiento real.
