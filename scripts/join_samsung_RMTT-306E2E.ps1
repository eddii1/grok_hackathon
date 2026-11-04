$ErrorActionPreference = "Continue"
$root = "D:\Grok hackathon"

function Wifi-Ip {
  $ips = @(Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias "Wi-Fi" -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -notlike "169.254.*" } |
    Select-Object -ExpandProperty IPAddress)
  if ($ips.Count -gt 0) { return $ips[0] }
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
for ($i = 0; $i -lt 20; $i++) {
  Start-Sleep -Seconds 1
  $ssid = Wifi-Ssid
  $ip = Wifi-Ip
  Write-Output "drone t=$i ssid=$ssid ip=$ip"
  if ($ssid -eq "RMTT-306E2E" -and $ip -like "192.168.10.*") { $joined = $true; break }
}

$code = 1
if ($joined) {
  python "$root\scripts\hello_matrix_RMTT-306E2E.py" --sta --ip 192.168.10.1
  $code = $LASTEXITCODE
} else {
  Write-Output "CONNECT_DRONE_FAILED"
}

netsh wlan set profileparameter name="Samsung" connectionmode=auto | Out-Host
netsh wlan connect name="Samsung" | Out-Host
$back = $false
for ($i = 0; $i -lt 25; $i++) {
  Start-Sleep -Seconds 1
  $ssid = Wifi-Ssid
  $ip = Wifi-Ip
  Write-Output "back t=$i ssid=$ssid ip=$ip"
  if ($ssid -eq "Samsung" -and $ip -and $ip -notlike "192.168.10.*") { $back = $true; break }
}
if (-not $back) { Write-Output "REJOIN_SAMSUNG_FAILED"; exit 1 }
if ($code -ne 0) { exit $code }

# The drone reboots onto the hotspot. Find it, then spell HELLO from here.
$shown = $false
for ($try = 1; $try -le 8; $try++) {
  Start-Sleep -Seconds 4
  Write-Output "LOOK $try"
  python "$root\scripts\hello_matrix_RMTT-306E2E.py"
  if ($LASTEXITCODE -eq 0) { $shown = $true; break }
}
if (-not $shown) { Write-Output "DRONE_NOT_ON_HOTSPOT"; exit 1 }
exit 0
