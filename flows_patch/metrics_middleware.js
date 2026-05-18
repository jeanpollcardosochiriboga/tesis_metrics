/**
 * Backend latency middleware for Node-RED §4 instrumentation.
 *
 * Writes one CSV line per HTTP-in request handled by Node-RED:
 *   ts, endpoint, method, processing_ms, status_code
 *
 * Append-only, fire-and-forget (does not block requests on I/O).
 *
 * Output path (inside container):
 *   /data/metrics_out/backend_latency.csv
 * which on the Pi host equals:
 *   /home/raspberry1/tesis_escenarioN/metrics_out/backend_latency.csv
 * because docker-compose bind-mounts ./:/data.
 *
 * The session.sh harness moves this file into sessions/<id>/ at end of session.
 *
 * Install:
 *   1. Copy this file to the project root (alongside settings.js, flows.json).
 *   2. Edit settings.js, at the top of module.exports:
 *        const metricsMW = require('./metrics_middleware');
 *      And inside module.exports:
 *        httpNodeMiddleware: metricsMW,
 *   3. docker-compose restart  (the container reloads settings.js)
 */
const fs = require('fs');
const path = require('path');

const OUT_DIR = process.env.METRICS_OUT_DIR || '/data/metrics_out';
const OUT_FILE = path.join(OUT_DIR, 'backend_latency.csv');
const HEADER = 'ts,endpoint,method,processing_ms,status_code\n';

try {
    fs.mkdirSync(OUT_DIR, { recursive: true });
    if (!fs.existsSync(OUT_FILE)) {
        fs.writeFileSync(OUT_FILE, HEADER);
    }
} catch (e) {
    console.warn('[metrics_middleware] could not init output:', e.message);
}

function csvEscape(s) {
    s = String(s == null ? '' : s);
    if (s.includes(',') || s.includes('"') || s.includes('\n')) {
        return '"' + s.replace(/"/g, '""') + '"';
    }
    return s;
}

module.exports = function metricsMiddleware(req, res, next) {
    const startNs = process.hrtime.bigint();
    const startMs = Date.now();

    res.on('finish', () => {
        try {
            const elapsedNs = process.hrtime.bigint() - startNs;
            const ms = Number(elapsedNs) / 1e6;
            const ts = (startMs / 1000).toFixed(3);
            const ep = csvEscape((req.baseUrl || '') + (req.path || req.url || ''));
            const line = `${ts},${ep},${req.method},${ms.toFixed(2)},${res.statusCode}\n`;
            fs.appendFile(OUT_FILE, line, (err) => {
                if (err) console.warn('[metrics_middleware] append failed:', err.message);
            });
        } catch (e) {
            // never throw from middleware
        }
    });

    next();
};
