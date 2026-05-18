# Instalación del formulario de encuesta (§4.1) en Node-RED

El form HTML es servido como **archivo estático** desde `httpStatic` del
contenedor de Node-RED. El POST de respuestas se atiende con dos nodos
(http-in + function) que escriben a `survey.csv`.

## Pasos por escenario

### 1. Copiar `form.html` y `survey_template.json` al directorio público

```bash
cp tesis/metrics/survey/form.html \
   Escritorio/tesis_escenario1/public/survey.html

cp tesis/metrics/survey/survey_template.json \
   Escritorio/tesis_escenario1/public/survey_template.json
```

El `settings.js` ya tiene `httpStatic: '/data/public'` (verificado para Esc1).
Si el directorio `public/` no existe, créalo:
```bash
mkdir -p Escritorio/tesis_escenario1/public
```

Tras esto, el form queda accesible en:
- `http://192.168.1.10:1881/survey.html?scenario=esc1`
- `http://192.168.1.10:1881/survey_template.json`

### 2. Agregar 2 nodos a `flows.json` (vía Node-RED UI)

a) **http-in node**: Method `POST`, URL `/api/survey`.
b) **function node** que recibe el JSON y appende a `survey.csv`. Cuerpo:

```js
const fs = global.get('fs') || require('fs');
const path = global.get('path') || require('path');
global.set('fs', fs); global.set('path', path);

const OUT = process.env.METRICS_OUT_DIR || '/data/metrics_out';
const FILE = path.join(OUT, 'survey.csv');

try { fs.mkdirSync(OUT, { recursive: true }); } catch(e) {}

const body = msg.payload || {};
const scenario = body.scenario || '';
const ts = (body.ts || Date.now()/1000).toFixed(3);
const answers = body.answers || {};

// Build a stable column order: every key found in payload + 3 fixed.
const keys = Object.keys(answers).sort();
const headerNeeded = !fs.existsSync(FILE);

function esc(s) {
    s = String(s == null ? '' : s);
    if (s.includes(',') || s.includes('"') || s.includes('\n')) {
        return '"' + s.replace(/"/g,'""') + '"';
    }
    return s;
}

if (headerNeeded) {
    fs.writeFileSync(FILE, 'ts,scenario,respondent_uuid,' + keys.join(',') + '\n');
}
const uuid = (Date.now().toString(36) + Math.random().toString(36).slice(2,8));
const row = [ts, esc(scenario), uuid, ...keys.map(k => esc(answers[k]))].join(',');
fs.appendFileSync(FILE, row + '\n');

msg.payload = { ok: true };
msg.statusCode = 200;
return msg;
```

c) **http-response node** conectado al output del function.

### 3. Redirigir el final del flujo del escenario al form

Al cerrar el flujo (página de "gracias por participar" del Esc1, Esc2 o Esc3),
agregar un botón o redirect a `/survey.html?scenario=esc1`.

### 4. Verificar

```bash
curl -X POST http://192.168.1.10:1881/api/survey \
  -H 'Content-Type: application/json' \
  -d '{"scenario":"esc1","ts":1747500000,"answers":{"sus1":"5","sus2":"2","ped1":"5","ped2":"4"}}'

tail -3 Escritorio/tesis_escenario1/metrics_out/survey.csv
```

## Salida

`metrics_out/survey.csv` (gitignored). Columnas:

| Columna | Tipo | Descripción |
|---|---|---|
| `ts` | float | Epoch en segundos cuando el cliente envió la respuesta |
| `scenario` | str | `esc1` / `esc2` / `esc3` |
| `respondent_uuid` | str | id anónimo único por respondiente (no PII) |
| `sus1..sus6` | int 1–5 | ítems SUS reducido |
| `ped1` | int 1–5 | comprensión percibida |
| `ped2` | int 1–5 | recomendaría la carrera |
| `mejoras` | str | texto libre opcional |
| `libre` | str | texto libre opcional |

Las columnas se generan automáticamente a partir de los `id` que estén
en `survey_template.json`. Editar el template no requiere cambiar el
function node.
