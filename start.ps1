# One-command startup for the IBVAP clone (backend + frontend).
# Run from anywhere:  powershell -ExecutionPolicy Bypass -File "C:\Users\Neha AJ\Desktop\prototype2\Lux\IBVAP\start.ps1"

$root = $PSScriptRoot
$dockerDesktopExe = "C:\Users\Neha AJ\AppData\Local\Programs\DockerDesktop\Docker Desktop.exe"

function Test-DockerRunning {
    try { docker info *> $null; return $LASTEXITCODE -eq 0 } catch { return $false }
}

# --- 1. Make sure Docker Desktop is running ---
if (-not (Test-DockerRunning)) {
    Write-Host "Starting Docker Desktop..." -ForegroundColor Cyan
    Start-Process $dockerDesktopExe
    $waited = 0
    while (-not (Test-DockerRunning)) {
        if ($waited -ge 90) {
            Write-Host "Docker still isn't up after 90s -- open Docker Desktop manually and re-run this script." -ForegroundColor Red
            exit 1
        }
        Start-Sleep -Seconds 3
        $waited += 3
    }
    Write-Host "Docker is up." -ForegroundColor Green
} else {
    Write-Host "Docker is already running." -ForegroundColor Green
}

# --- 2. Free the shared ports from the other project's stack, if it's up ---
$otherStack = "C:\Users\Neha AJ\Desktop\prototype2\M0-M3\ibvap"
if (Test-Path "$otherStack\docker-compose.yml") {
    $running = docker ps --filter "name=ibvap-nginx-1" --format "{{.Names}}" 2>$null
    if ($running) {
        Write-Host "Stopping the other project's stack to free shared ports..." -ForegroundColor Yellow
        Push-Location $otherStack
        docker compose down
        Pop-Location
    }
}

# --- 3. Start the backend ---
Write-Host "Starting backend..." -ForegroundColor Cyan
Push-Location "$root\backend"
docker compose up -d
Pop-Location

Write-Host "Waiting for services to become healthy..." -ForegroundColor Cyan
$deadline = (Get-Date).AddMinutes(3)
do {
    Start-Sleep -Seconds 5
    Push-Location "$root\backend"
    $unhealthy = docker compose ps --format json 2>$null | ForEach-Object { $_ | ConvertFrom-Json } |
        Where-Object { $_.Health -and $_.Health -ne "healthy" }
    Pop-Location
} while ($unhealthy -and (Get-Date) -lt $deadline)

if ($unhealthy) {
    Write-Host "Some services still aren't healthy after 3 minutes -- check with 'docker compose ps' in backend/." -ForegroundColor Yellow
    $unhealthy | ForEach-Object { Write-Host "  - $($_.Service): $($_.Health)" -ForegroundColor Yellow }
} else {
    Write-Host "Backend is healthy." -ForegroundColor Green
}

# --- 4. Start the frontend in its own window ---
Write-Host "Starting frontend in a new window..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\frontend'; npm run dev"

Write-Host ""
Write-Host "Backend:  http://localhost:8080" -ForegroundColor Green
Write-Host "Frontend: http://localhost:5173" -ForegroundColor Green
Write-Host "Log in with the admin credentials from backend\.env (BOOTSTRAP_ADMIN_USERNAME/PASSWORD)."
