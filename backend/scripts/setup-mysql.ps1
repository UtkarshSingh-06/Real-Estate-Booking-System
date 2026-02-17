# Setup and run MySQL for Real Estate Booking System
# MySQL 8.4 is installed at: C:\Program Files\MySQL\MySQL Server 8.4

$mysqlBin = "C:\Program Files\MySQL\MySQL Server 8.4\bin"
if (-not (Test-Path $mysqlBin)) {
    $mysqlBin = "C:\Program Files\MySQL\MySQL Server 8.0\bin"
}

# 1. If MySQL was just installed, run the Configurator first (one-time)
if (-not (Test-Path "C:\Program Files\MySQL\MySQL Server 8.4\data")) {
    Write-Host "MySQL data directory not found. Running MySQL Configurator..."
    Write-Host "In the wizard: set root password and choose 'Configure as Windows Service'."
    Start-Process "$mysqlBin\mysql_configurator.exe" -Verb RunAs -Wait
}

# 2. Start MySQL Windows service (run PowerShell as Administrator)
$services = Get-Service -ErrorAction SilentlyContinue | Where-Object { $_.Name -match "MySQL" }
if ($services) {
    $svc = $services | Select-Object -First 1
    Write-Host "Starting MySQL service: $($svc.Name)"
    try {
        Start-Service -Name $svc.Name -ErrorAction Stop
        Start-Sleep -Seconds 3
        Write-Host "MySQL service status: $((Get-Service -Name $svc.Name).Status)"
    } catch {
        Write-Host "Start failed (try running this script as Administrator): $_"
    }
} else {
    Write-Host "MySQL Windows service not found. Run MySQL Configurator from Start Menu first."
}

# 3. Create database
$env:Path = "$mysqlBin;$env:Path"
Write-Host ""
Write-Host "Create the database (use the root password you set in Configurator):"
Write-Host '  & "$mysqlBin\mysql.exe" -u root -p -e "CREATE DATABASE IF NOT EXISTS realestate_db;"'
Write-Host ""
Write-Host "Then in backend\.env set: DB_PASSWORD=<your_root_password>"
