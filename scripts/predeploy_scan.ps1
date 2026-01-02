param(
  [ValidateSet("report", "enforce")]
  [string]$Mode = "report",
  [switch]$Fix,
  [switch]$RemediateIac
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
  try {
    $global:LASTEXITCODE = 0

    # Capture output to prevent it from becoming part of the function return value.
    # Still print it for the user.
    $output = & $Cmd 2>&1
    if ($null -ne $output) {
      $output | Out-Host
    }

    $rc = $global:LASTEXITCODE
    if ($rc -eq $null) { $rc = 0 }
    if ($rc -ne 0) {
      Write-Host "[$Name] FAILED (exit=$rc)"
      if ($Enforce) { return 1 }
    }
    return 0
  } catch {
    Write-Host "[$Name] ERROR"
    $_ | Out-Host
    if ($Enforce) { return 1 }
    return 0
  }
}

$enforce = ($Mode -eq "enforce")
$failCount = 0

# Run from repo root (script lives in ./scripts)
Set-Location (Resolve-Path (Join-Path $PSScriptRoot ".."))

Write-Host "Pre-deploy scan mode: $Mode"
Write-Host "Auto-fix: $Fix"
Write-Host "IaC runbook remediation: $RemediateIac"
Write-Host "Repo: $(Get-Location)"

if ($Fix) {
  Write-Host ""
  Write-Host "==> fix: trim trailing whitespace in YAML (*.yml/*.yaml)"
  try {
    $yamlFiles = Get-ChildItem -Recurse -File -Include *.yml,*.yaml |
      Where-Object { $_.FullName -notmatch '\\\.terraform\\' }

    foreach ($f in $yamlFiles) {
      $raw = Get-Content -LiteralPath $f.FullName -Raw
      $fixed = $raw -replace '(?m)[ \t]+$',''
      if ($fixed -ne $raw) {
        Set-Content -LiteralPath $f.FullName -Value $fixed -NoNewline
      }
    }
    Write-Host "YAML whitespace fix: done ($($yamlFiles.Count) files scanned)"
  } catch {
    Write-Host "[fix:yml] ERROR"
    $_ | Out-Host
  }

  Write-Host ""
  Write-Host "==> fix: terraform fmt (best effort)"
  try {
    if (Get-Command terraform -ErrorAction SilentlyContinue) {
      terraform fmt -recursive terraform | Out-Host
    } else {
      Write-Host "terraform not found on PATH; skipping terraform fmt"
    }
  } catch {
    Write-Host "[fix:terraform] ERROR"
    $_ | Out-Host
  }

  Write-Host ""
  Write-Host "==> fix: ansible-lint --fix (Docker, best effort)"
  try {
    docker version | Out-Null
    docker run --rm -v "${PWD}:/work" -w /work cytopia/ansible-lint:latest ansible-lint --fix ansible/*.yml -p | Out-Host
  } catch {
    Write-Host "[fix:ansible-lint] ERROR"
    $_ | Out-Host
  }
}

if ($RemediateIac) {
  Write-Host ""
  Write-Host "==> remediate: IaC runbook (Terraform SG world-open -> admin_cidr)"
  $didRemediate = $false

  # Preferred path: run the Ansible runbook via Docker (works well on Windows if Docker Desktop Linux engine is running)
  try {
    docker version | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "docker version failed (is Docker Desktop running / Linux engine enabled?)" }
    docker run --rm -v "${PWD}:/work" -w /work cytopia/ansible-lint:latest `
      ansible-playbook -i localhost, -c local ansible/runbooks/iac_remediate_openstack_sg.yml `
      --extra-vars "iac_mode=secure admin_cidr_expr=var.admin_cidr"
    if ($LASTEXITCODE -ne 0) { throw "ansible-playbook failed in Docker" }
    $didRemediate = $true
  } catch {
    Write-Host "[remediate:iac] Docker/Ansible runbook not available on this machine (will fallback to PowerShell edit)."
  }

  # Fallback: do the same remediation locally (no Docker/Ansible needed).
  if (-not $didRemediate) {
    try {
      $tfPath = Join-Path $PWD "terraform/main.tf"
      if (-not (Test-Path $tfPath)) {
        throw "Terraform file not found: $tfPath"
      }

      $content = Get-Content -LiteralPath $tfPath -Raw

      # Simple, safe-for-this-repo remediation:
      # Replace any world-open remote_ip_prefix line with var.admin_cidr.
      # (In this repo, only the demo SG rules use 0.0.0.0/0 for remote_ip_prefix.)
      $content2 = [regex]::Replace(
        $content,
        '(?m)^(\s*remote_ip_prefix\s*=\s*)"0\.0\.0\.0/0"\s*$',
        '$1var.admin_cidr'
      )

      if ($content2 -ne $content) {
        Set-Content -LiteralPath $tfPath -Value $content2 -NoNewline
        Write-Host "PowerShell remediation applied to terraform/main.tf (remote_ip_prefix -> var.admin_cidr)."
      } else {
        Write-Host "PowerShell remediation: no changes needed (already remediated?)."
      }
    } catch {
      Write-Host "[remediate:iac] ERROR"
      $_ | Out-Host
      if ($enforce) { $failCount += 1 }
    }
  }
}

# 1) YAML lint
$failCount += Invoke-Tool -Name "yamllint" -Enforce:$enforce -Cmd {
  python -m pip install -r .ci/requirements-iac.txt | Out-Host
  yamllint -f parsable .
}

# 2) Terraform misconfiguration scan (Checkov)
$failCount += Invoke-Tool -Name "checkov (terraform/)" -Enforce:$enforce -Cmd {
  python -m pip install -r .ci/requirements-iac.txt | Out-Host
  # Avoid Windows file-association issues by running checkov as a Python module
  python -m checkov.main -d terraform --quiet
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


