# PCR3 Casper - Channel Restart Script
# Usage:
#   .\restart_channel.ps1 1           (restart by channel number)
#   .\restart_channel.ps1 GFXPVW      (restart by name)
#   .\restart_channel.ps1 all         (restart every channel)

param(
    [Parameter(Mandatory=$true, Position=0)]
    [string]$Target
)

$AmcpHost = "127.0.0.1"
$AmcpPort = 5250

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

function Restart-Channel {
    param($ch)
    Write-Host "Restarting CH$($ch.Channel) [$($ch.Name)]..." -ForegroundColor Yellow

    $stopResult = Send-AmcpCommand "STOP $($ch.Channel)-1"
    if ($stopResult) { Write-Host "  STOP  -> $stopResult" }

    Start-Sleep -Milliseconds 500

    $playCmd = "PLAY $($ch.Channel)-1 [HTML] `"$($ch.Url)`""
    $playResult = Send-AmcpCommand $playCmd
    if ($playResult) { Write-Host "  PLAY  -> $playResult" }

    Write-Host "  Done. NDI 'PCR3 $($ch.Name)' is live." -ForegroundColor Green
}

# Resolve target
if ($Target -eq "all") {
    Write-Host "Restarting all channels..." -ForegroundColor Cyan
    foreach ($ch in $Channels) {
        Restart-Channel $ch
        Start-Sleep -Milliseconds 300
    }
} elseif ($Target -match '^\d+$') {
    $num = [int]$Target
    $ch  = $Channels | Where-Object { $_.Channel -eq $num }
    if ($null -eq $ch) {
        Write-Host "ERROR: No channel with number $num. Valid: 1-5" -ForegroundColor Red
        exit 1
    }
    Restart-Channel $ch
} else {
    $ch = $Channels | Where-Object { $_.Name -eq $Target.ToUpper() }
    if ($null -eq $ch) {
        $validNames = ($Channels | ForEach-Object { $_.Name }) -join ", "
        Write-Host "ERROR: No channel named '$Target'. Valid names: $validNames" -ForegroundColor Red
        exit 1
    }
    Restart-Channel $ch
}
