$ErrorActionPreference = "Continue"
$root = "D:\Grok hackathon"

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

netsh wlan set profileparameter name="Samsung" connectionmode=manual | Out-Host
netsh wlan add profile filename="$root\scripts\rmtt-306E2E.xml" | Out-Host
netsh wlan disconnect | Out-Host
Start-Sleep -Seconds 1
netsh wlan connect name="RMTT-306E2E" | Out-Host

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
  if ($ssid -eq "RMTT-306E2E" -and $ip -like "192.168.10.*") {
    $joined = $true
    $droneLocal = $ip
    break
  }
}

$sta = 1
if ($joined) {
  python "$root\scripts\station_once_RMTT-306E2E.py" $droneLocal
  $sta = $LASTEXITCODE
} else {
  Write-Output "CONNECT_DRONE_FAILED"
}

netsh wlan set profileparameter name="Samsung" connectionmode=auto | Out-Host
netsh wlan connect name="Samsung" | Out-Host
$back = $false
$hotspotIp = ""
for ($i = 0; $i -lt 25; $i++) {
  Start-Sleep -Seconds 1
  $ssid = Wifi-Ssid
  $hotspotIp = Wifi-Ip
  Write-Output "back t=$i ssid=$ssid ip=$hotspotIp"
  if ($ssid -eq "Samsung" -and $hotspotIp -like "10.*") { $back = $true; break }
}
if (-not $back) { Write-Output "REJOIN_SAMSUNG_FAILED"; exit 1 }
Write-Output "STA_EXIT=$sta"

$deadline = (Get-Date).AddSeconds(60)
$code = 1
while ((Get-Date) -lt $deadline) {
  $hotspotIp = Wifi-Ip
  Write-Output "LOOK from $hotspotIp"
  python "$root\scripts\camera_test_RMTT-306E2E.py" $hotspotIp
  $code = $LASTEXITCODE
  if ($code -eq 0) { break }
  Start-Sleep -Seconds 4
}
if ($code -ne 0) { Write-Output "CAMERA_NOT_READY" }
exit $code
