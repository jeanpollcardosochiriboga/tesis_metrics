module.exports = {
    flowFile: 'flows.json',
    credentialSecret: 'tesis-ops-console-2026',
    flowFilePretty: true,
    uiPort: process.env.PORT || 1880,
    diagnostics: { enabled: true, ui: true },
    runtimeState: { enabled: false, ui: false },
    logging: { console: { level: "info", metrics: false, audit: false } },
    exportGlobalContextKeys: false,
    externalModules: {},
    editorTheme: {
        page: { title: "Tesis — Operator Console" },
        header: { title: "Operator Console" },
        palette: { editable: true },
        projects: { enabled: false }
    },
    ui: { path: "ui" },
    functionExternalModules: true,
    functionGlobalContext: {
        PI_HOST: process.env.PI_HOST || "192.168.1.10",
        PI_USER: process.env.PI_USER || "raspberry1",
        ROUTER_HOST: process.env.ROUTER_HOST || "192.168.1.1",
        ROUTER_USER: process.env.ROUTER_USER || "root",
    },
};
