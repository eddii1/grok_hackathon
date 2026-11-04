$ErrorActionPreference = "Continue"
$root = "D:\Grok hackathon"
$droneName = "TELLO-99484E"
$hotspot = "Samsung"

function Wifi-Ip {
  $ips = @(Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias "Wi-Fi" -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -notlike "169.254.*" -and $_.IPAddress -notlike "192.168.10.*" } |
    Select-Object -ExpandProperty IPAddress)
  if ($ips.Count -gt 0) { return $ips[0] }
  $any = @(Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias "Wi-Fi" -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -notlike "169.254.*" } |
    Select-Object -ExpandProperty IPAddress)
  if ($any.Count -gt 0) { return $any[0] }
  return ""
}

function Wifi-Ssid {
  $raw = netsh wlan show interfaces | Out-String
  return ([regex]::Match($raw, "(?m)^\s+SSID\s+:\s*(.+)$")).Groups[1].Value.Trim()
}

Write-Output ">>> Step 1: Disconnecting from $hotspot and joining $droneName..."
netsh wlan set profileparameter name="$hotspot" connectionmode=manual | Out-Host
netsh wlan add profile filename="$root\scripts\tello-99484E.xml" | Out-Host
netsh wlan disconnect | Out-Host
Start-Sleep -Seconds 1
netsh wlan connect name="$droneName" | Out-Host

$joined = $false
$droneLocal = ""
for ($i = 0; $i -lt 20; $i++) {
  Start-Sleep -Seconds 1
  $ssid = Wifi-Ssid
  $rawIp = @(Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias "Wi-Fi" -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -like "192.168.10.*" } |
    Select-Object -ExpandProperty IPAddress)
  $ip = ""
  if ($rawIp.Count -gt 0) { $ip = $rawIp[0] }
  Write-Output "drone t=$i ssid=$ssid ip=$ip"
  if ($ssid -eq $droneName -and $ip -like "192.168.10.*") {
    $joined = $true
    $droneLocal = $ip
    break
  }
}

$sta = 1
if ($joined) {
  Write-Output ">>> Step 2: Sending Station Mode command to $droneName..."
  python "$root\scripts\station_once_TELLO-99484E.py" $droneLocal
  $sta = $LASTEXITCODE
} else {
  Write-Output "CONNECT_DRONE_FAILED for $droneName"
}

Write-Output ">>> Step 3: Reconnecting PC to $hotspot..."
netsh wlan set profileparameter name="$hotspot" connectionmode=auto | Out-Host
netsh wlan connect name="$hotspot" | Out-Host
$back = $false
$hotspotIp = ""
for ($i = 0; $i -lt 25; $i++) {
  Start-Sleep -Seconds 1
  $ssid = Wifi-Ssid
  $hotspotIp = Wifi-Ip
  Write-Output "back t=$i ssid=$ssid ip=$hotspotIp"
  if ($ssid -eq "$hotspot" -and $hotspotIp -like "10.*") { $back = $true; break }
}

if (-not $back) { Write-Output "REJOIN_HOTSPOT_FAILED"; exit 1 }

Write-Output ">>> Step 4: Waiting for $droneName to appear on $hotspot and starting live camera..."
$deadline = (Get-Date).AddSeconds(45)
$code = 1
while ((Get-Date) -lt $deadline) {
  $hotspotIp = Wifi-Ip
  python "$root\scripts\camera_stream_TELLO-99484E.py" $hotspotIp
  $code = $LASTEXITCODE
  if ($code -eq 0) { break }
  Start-Sleep -Seconds 3
}

exit $code
