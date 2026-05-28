param(
    [ValidateSet("env", "build", "flash", "monitor", "build-flash", "full")]
    [string]$Action = "env",
    [string]$ProjectPath = "firmware/controller",
    [string]$Port = "",
    [string]$ExportScriptPath = "",
    [string]$Target = "esp32s3"
)

$ErrorActionPreference = "Stop"

function Get-VersionScore {
    param([string]$Path)

    $m = [regex]::Match($Path, "v?(\d+)\.(\d+)(?:\.(\d+))?")
    if (-not $m.Success) {
        return 0
    }

    $major = [int]$m.Groups[1].Value
    $minor = [int]$m.Groups[2].Value
    $patch = 0
    if ($m.Groups[3].Success) {
        $patch = [int]$m.Groups[3].Value
    }

    return ($major * 1000000) + ($minor * 1000) + $patch
}

function Find-EspIdfExportScript {
    $candidates = New-Object System.Collections.Generic.List[string]

    if ($env:IDF_PATH) {
        $candidates.Add((Join-Path $env:IDF_PATH "export.ps1"))
    }

    $roots = @(
        (Join-Path $env:USERPROFILE "esp"),
        "C:\Espressif\frameworks",
        "C:\Espressif"
    )

    foreach ($root in $roots) {
        if (-not (Test-Path $root)) {
            continue
        }

        $matches = Get-ChildItem -Path $root -Filter "export.ps1" -File -Recurse -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -match "esp-idf|idf" }

        foreach ($m in $matches) {
            $candidates.Add($m.FullName)
        }
    }

    $valid = $candidates |
        Where-Object { Test-Path $_ } |
        Select-Object -Unique

    if (-not $valid -or $valid.Count -eq 0) {
        return $null
    }

    return $valid |
        Sort-Object @{ Expression = { Get-VersionScore $_ }; Descending = $true }, @{ Expression = { $_.Length }; Descending = $true } |
        Select-Object -First 1
}

function Use-EspIdfEnvironment {
    $exportScript = $null

    if (-not [string]::IsNullOrWhiteSpace($ExportScriptPath)) {
        if (-not (Test-Path $ExportScriptPath)) {
            throw "Provided ExportScriptPath does not exist: $ExportScriptPath"
        }
        $exportScript = (Resolve-Path $ExportScriptPath).Path
    }
    else {
        $exportScript = Find-EspIdfExportScript
    }

    if (-not $exportScript) {
        throw "ESP-IDF export.ps1 was not found. Install ESP-IDF and try again."
    }

    Write-Host "[ESP-IDF] export script: $exportScript"
    & $exportScript

    $idf = Get-Command idf.py -ErrorAction SilentlyContinue
    if (-not $idf) {
        throw "idf.py was not found after export.ps1. Check ESP-IDF installation."
    }

    Write-Host "[ESP-IDF] idf.py: $($idf.Source)"
}

function Invoke-Idf {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Args,
        [Parameter(Mandatory = $true)]
        [string]$WorkDir
    )

    Push-Location $WorkDir
    try {
        & idf.py @Args
        if ($LASTEXITCODE -ne 0) {
            throw "idf.py failed (exit=$LASTEXITCODE): idf.py $($Args -join ' ')"
        }
    }
    finally {
        Pop-Location
    }
}

function Ensure-IdfTarget {
    param(
        [Parameter(Mandatory = $true)]
        [string]$WorkDir,
        [Parameter(Mandatory = $true)]
        [string]$ExpectedTarget
    )

    $sdkconfigPath = Join-Path $WorkDir "sdkconfig"
    $current = ""

    if (Test-Path $sdkconfigPath) {
        $line = Select-String -Path $sdkconfigPath -Pattern '^CONFIG_IDF_TARGET="([^"]+)"' | Select-Object -First 1
        if ($line -and $line.Matches.Count -gt 0) {
            $current = $line.Matches[0].Groups[1].Value
        }
    }

    if ($current -ne $ExpectedTarget) {
        Write-Host "[Target] switching from '$current' to '$ExpectedTarget'"
        Invoke-Idf -Args @("set-target", $ExpectedTarget) -WorkDir $WorkDir
    }
    else {
        Write-Host "[Target] already '$ExpectedTarget'"
    }
}

function Resolve-SerialPort {
    param([string]$InputPort)

    if (-not [string]::IsNullOrWhiteSpace($InputPort) -and $InputPort.ToLower() -ne "auto") {
        return $InputPort
    }

    $ports = @()
    try {
        $ports = Get-CimInstance Win32_SerialPort -ErrorAction Stop
    }
    catch {
        $ports = @()
    }

    if (-not $ports -or $ports.Count -eq 0) {
        throw "No COM ports were detected. Connect the board and retry with -Port COMx."
    }

    $preferred = $ports | Where-Object {
        ($_.Description -match "USB|CP210|CH340|CH910|Silicon Labs|Espressif|JTAG") -or
        ($_.PNPDeviceID -match "VID_")
    }

    $selected = $null
    if ($preferred -and $preferred.Count -gt 0) {
        $selected = $preferred | Select-Object -First 1
    }
    else {
        $selected = $ports | Select-Object -First 1
    }

    Write-Host "[Port] auto-selected $($selected.DeviceID) ($($selected.Description))"
    if ($ports.Count -gt 1) {
        Write-Host "[Port] detected: $($ports.DeviceID -join ', ')"
    }

    return $selected.DeviceID
}

$resolvedProject = (Resolve-Path $ProjectPath).Path
Use-EspIdfEnvironment

Write-Host "[Project] $resolvedProject"

switch ($Action) {
    "env" {
        Write-Host "[Done] ESP-IDF environment is active."
        Write-Host "[Hint] default target is '$Target'"
    }
    "build" {
        Ensure-IdfTarget -WorkDir $resolvedProject -ExpectedTarget $Target
        Invoke-Idf -Args @("build") -WorkDir $resolvedProject
    }
    "flash" {
        Ensure-IdfTarget -WorkDir $resolvedProject -ExpectedTarget $Target
        $resolvedPort = Resolve-SerialPort -InputPort $Port
        Invoke-Idf -Args @("-p", $resolvedPort, "flash") -WorkDir $resolvedProject
    }
    "monitor" {
        Ensure-IdfTarget -WorkDir $resolvedProject -ExpectedTarget $Target
        $resolvedPort = Resolve-SerialPort -InputPort $Port
        Invoke-Idf -Args @("-p", $resolvedPort, "monitor") -WorkDir $resolvedProject
    }
    "build-flash" {
        Ensure-IdfTarget -WorkDir $resolvedProject -ExpectedTarget $Target
        $resolvedPort = Resolve-SerialPort -InputPort $Port
        Invoke-Idf -Args @("-p", $resolvedPort, "build", "flash") -WorkDir $resolvedProject
    }
    "full" {
        Ensure-IdfTarget -WorkDir $resolvedProject -ExpectedTarget $Target
        $resolvedPort = Resolve-SerialPort -InputPort $Port
        Invoke-Idf -Args @("-p", $resolvedPort, "build", "flash", "monitor") -WorkDir $resolvedProject
    }
}
