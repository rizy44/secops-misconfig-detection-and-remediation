param(
  [ValidateSet("report", "enforce")]
  [string]$Mode = "report"
)

$ErrorActionPreference = "Stop"

function Invoke-Tool {
  param(
    [Parameter(Mandatory=$true)][string]$Name,
    [Parameter(Mandatory=$true)][scriptblock]$Cmd,
    [switch]$Enforce
  )

  Write-Host ""
  Write-Host "==> $Name"
  $global:LASTEXITCODE = 0
  & $Cmd
  $rc = $global:LASTEXITCODE
  if ($rc -eq $null) { $rc = 0 }
  if ($rc -ne 0) {
    Write-Host "[$Name] FAILED (exit=$rc)"
    if ($Enforce) { return 1 }
  }
  return 0
}

$enforce = ($Mode -eq "enforce")
$failCount = 0

# Run from repo root (script lives in ./scripts)
Set-Location (Resolve-Path (Join-Path $PSScriptRoot ".."))

Write-Host "Pre-deploy scan mode: $Mode"
Write-Host "Repo: $(Get-Location)"

# 1) YAML lint
$failCount += Invoke-Tool -Name "yamllint" -Enforce:$enforce -Cmd {
  python -m pip install -r .ci/requirements-iac.txt | Out-Host
  yamllint -f parsable .
}

# 2) Terraform misconfiguration scan (Checkov)
$failCount += Invoke-Tool -Name "checkov (terraform/)" -Enforce:$enforce -Cmd {
  python -m pip install -r .ci/requirements-iac.txt | Out-Host
  checkov -d terraform --quiet
}

# 3) Trivy IaC scan (Docker) - optional (best effort)
$failCount += Invoke-Tool -Name "trivy config (Docker)" -Enforce:$enforce -Cmd {
  docker version | Out-Null
  docker run --rm -v "${PWD}:/work" -w /work aquasec/trivy:latest config --severity HIGH,CRITICAL --exit-code 1 .
}

# 4) Ansible lint (Docker) - optional (best effort)
$failCount += Invoke-Tool -Name "ansible-lint (Docker)" -Enforce:$enforce -Cmd {
  docker version | Out-Null
  docker run --rm -v "${PWD}:/work" -w /work cytopia/ansible-lint:latest ansible-lint ansible/*.yml -p
}

Write-Host ""
if ($enforce -and $failCount -gt 0) {
  Write-Host "Pre-deploy scan: FAILED ($failCount failing checks)."
  exit 1
}

Write-Host "Pre-deploy scan: completed (Mode=$Mode)."
exit 0


