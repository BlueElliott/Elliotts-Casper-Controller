# PCR3 Casper Startup Script
# Launches CasparCG and loads all 5 Singular.live HTML sources via AMCP

$CasparExe = "$PSScriptRoot\casparcg.exe"
$AmcpHost  = "127.0.0.1"
$AmcpPort  = 5250
$StartupDelay = 8  # seconds to wait for CasparCG to fully initialise

$Channels = @(
    @{ Channel = 1; Name = "GFXPVW"; Url = "https://app.singular.live/output/66B4M4gG2cjcbEEP51ORwU/Output?aspect=16:9&g_custom1=GFXPVW" },
    @{ Channel = 2; Name = "GFX1";   Url = "https://app.singular.live/output/66B4M4gG2cjcbEEP51ORwU/Output?aspect=16:9&g_custom1=GFX1"   },
    @{ Channel = 3; Name = "GFX2";   Url = "https://app.singular.live/output/66B4M4gG2cjcbEEP51ORwU/Output?aspect=16:9&g_custom1=GFX2"   },
    @{ Channel = 4; Name = "GFX3";   Url = "https://app.singular.live/output/66B4M4gG2cjcbEEP51ORwU/Output?aspect=16:9&g_custom1=GFX3"   },
    @{ Channel = 5; Name = "GFX4";   Url = "https://app.singular.live/output/66B4M4gG2cjcbEEP51ORwU/Output?aspect=16:9&g_custom1=GFX4"   }
)

function Send-AmcpCommand {
    param([string]$Command)
    try {
        $tcp    = [System.Net.Sockets.TcpClient]::new($AmcpHost, $AmcpPort)
        $stream = $tcp.GetStream()
        $writer = [System.IO.StreamWriter]::new($stream)
        $reader = [System.IO.StreamReader]::new($stream)
        $writer.AutoFlush = $true

        $writer.WriteLine($Command)
        Start-Sleep -Milliseconds 300
        $response = ""
        while ($stream.DataAvailable) {
            $response += $reader.ReadLine() + "`n"
        }
        $tcp.Close()
        return $response.Trim()
    } catch {
        return "ERROR: $_"
    }
}

# --- Launch CasparCG ---
if (-not (Test-Path $CasparExe)) {
    Write-Host "ERROR: casparcg.exe not found at $CasparExe" -ForegroundColor Red
    Write-Host "Place this script in the same folder as casparcg.exe and try again."
    exit 1
}

Write-Host "Starting CasparCG..." -ForegroundColor Cyan
Start-Process -FilePath $CasparExe -WorkingDirectory $PSScriptRoot

Write-Host "Waiting $StartupDelay seconds for CasparCG to initialise..." -ForegroundColor Yellow
Start-Sleep -Seconds $StartupDelay

# --- Load HTML sources ---
foreach ($ch in $Channels) {
    $cmd = "PLAY $($ch.Channel)-1 [HTML] `"$($ch.Url)`""
    Write-Host "CH$($ch.Channel) [$($ch.Name)]: $cmd" -ForegroundColor Green
    $result = Send-AmcpCommand $cmd
    if ($result) { Write-Host "  -> $result" }
    Start-Sleep -Milliseconds 500
}

Write-Host ""
Write-Host "All channels loaded. NDI outputs are live:" -ForegroundColor Cyan
foreach ($ch in $Channels) {
    Write-Host "  CH$($ch.Channel) -> NDI: 'PCR3 $($ch.Name)'" -ForegroundColor White
}
