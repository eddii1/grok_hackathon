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
  python "$root\scripts\hop_hello_RMTT-306E2E.py"
  $code = $LASTEXITCODE
} else {
  Write-Output "CONNECT_DRONE_FAILED"
}

netsh wlan set profileparameter name="Samsung" connectionmode=auto | Out-Host
netsh wlan connect name="Samsung" | Out-Host
for ($i = 0; $i -lt 20; $i++) {
  Start-Sleep -Seconds 1
  $ssid = Wifi-Ssid
  $ip = Wifi-Ip
  Write-Output "back t=$i ssid=$ssid ip=$ip"
  if ($ssid -eq "Samsung" -and $ip -and $ip -notlike "192.168.10.*") { break }
}
exit $code
