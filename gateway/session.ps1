<#
.SYNOPSIS
  Wrapper de la LAPTOP (gateway Windows) para manejar sesiones de metricas que
  corren EN EL PI. La laptop NUNCA recolecta: este script solo dispara session.sh
  por SSH en el Pi y descarga (scp) los CSV para graficar localmente.

.DESCRIPTION
  Premisa (pedido del tutor): el Pi recolecta TODAS las metricas; la laptop solo
  visualiza y, como mucho, descarga los CSV. Por eso aqui no se invoca ningun
  collector: solo SSH (passthrough) + SCP (descarga).

.PARAMETER Command
  start <esc> | deploy | log <evento> [notas] | status | end | pull [id]

.EXAMPLE
  .\session.ps1 start esc1
  .\session.ps1 deploy
  .\session.ps1 log montaje_fisico_s 95
  .\session.ps1 status
  .\session.ps1 end          # cierra en el Pi y descarga la carpeta de sesion
  .\session.ps1 pull 2026-05-27_esc1   # re-descarga una sesion ya cerrada
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)] [string]$Command,
    [Parameter(Position = 1, ValueFromRemainingArguments = $true)] [string[]]$Rest
)

$ErrorActionPreference = 'Stop'

# --- Config (ajustar solo si cambian IP/usuario/ruta) ------------------------
$PiUser   = $env:PI_USER;    if (-not $PiUser)   { $PiUser   = 'raspberry1' }
$PiHost   = $env:PI_HOST;    if (-not $PiHost)   { $PiHost   = '192.168.1.10' }
$PiRepo   = $env:PI_REPO;    if (-not $PiRepo)   { $PiRepo   = '~/tesis_metrics_repo' }
$Target   = "$PiUser@$PiHost"
# Carpeta local donde se descargan las sesiones para graficar (junto a este repo).
$LocalSessions = Join-Path (Split-Path $PSScriptRoot -Parent) 'sessions'

function Invoke-PiSession {
    param([string[]]$SessionArgs)
    # Passthrough: corre session.sh EN EL PI. Nada se ejecuta localmente.
    $quoted = ($SessionArgs | ForEach-Object { "'$($_ -replace "'", "'\''")'" }) -join ' '
    $remote = "cd $PiRepo && ./session.sh $quoted"
    & ssh -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new $Target $remote
    # NOTA: no envolver llamadas a esta funcion en `(...)`: PowerShell capturaria
    # la salida de ssh como pipeline y dejaria la consola en blanco. Llamar directo
    # y usar $LASTEXITCODE.
}

function Get-LatestSessionId {
    (& ssh -o ConnectTimeout=8 $Target "ls -t $PiRepo/sessions 2>/dev/null | head -1").Trim()
}

function Pull-Session {
    param([string]$Id)
    if (-not $Id) { $Id = Get-LatestSessionId }
    if (-not $Id) { Write-Warning 'No hay carpeta de sesion en el Pi.'; return }
    New-Item -ItemType Directory -Force -Path $LocalSessions | Out-Null
    Write-Host "[pull] descargando sesion '$Id' del Pi -> $LocalSessions"
    & scp -r -o StrictHostKeyChecking=accept-new "${Target}:$PiRepo/sessions/$Id" $LocalSessions
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[pull] OK -> $(Join-Path $LocalSessions $Id)"
        Write-Host "[pull] graficar:  python plot_scenario.py sessions/$Id"
    } else {
        Write-Warning "[pull] scp fallo (rc=$LASTEXITCODE)"
    }
}

switch ($Command) {
    'start'  { Invoke-PiSession (@('start') + $Rest); exit $LASTEXITCODE }
    'deploy' { Invoke-PiSession @('deploy');           exit $LASTEXITCODE }
    'log'    { Invoke-PiSession (@('log')    + $Rest); exit $LASTEXITCODE }
    'status' { Invoke-PiSession @('status');           exit $LASTEXITCODE }
    'end'    {
        $id = Get-LatestSessionId
        Invoke-PiSession @('end')
        $rc = $LASTEXITCODE
        Pull-Session -Id $id
        exit $rc
    }
    'pull'   { Pull-Session -Id ($Rest | Select-Object -First 1); exit 0 }
    default  {
        Write-Host 'Uso: .\session.ps1 {start <esc>|deploy|log <evento> [notas]|status|end|pull [id]}'
        Write-Host 'La laptop solo dispara la sesion en el Pi (SSH) y descarga los CSV (SCP).'
        exit 2
    }
}
