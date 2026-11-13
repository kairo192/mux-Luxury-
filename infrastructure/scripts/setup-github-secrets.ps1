<#
=============================================================================
 Mus Luxury - one-time setup of the keys GitHub needs (run on YOUR Windows PC)

 What it does, with nothing to type by hand:
   1. Checks the app-update signing key (Tauri). Its PUBLIC half is committed
      (apps/desktop-cms/src-tauri/updater-key.pub) and every installed CMS only
      accepts updates signed with the matching private key: the owner received
      that private key file + password; put them in %USERPROFILE%\.tauri\ as
      mux_luxury.key and mux_luxury.key.password. A new key is NEVER created
      while a public key is committed (it would make every update fail).
   2. Creates the SSH deploy key GitHub Actions uses to publish to the VPS.
   3. If the GitHub CLI (gh) is installed and logged in, stores everything in
      the repository directly:
        secrets   TAURI_SIGNING_PRIVATE_KEY, TAURI_SIGNING_PRIVATE_KEY_PASSWORD,
                  PRODUCTION_SSH_PRIVATE_KEY, PRODUCTION_SSH_USER, PRODUCTION_SSH_HOST
        variables PRODUCTION_URL, PRODUCTION_HEALTH_URL
   4. Prints the ONE line to give to the VPS (public deploy key).

 The private keys are created on this PC and never printed. Existing keys
 are re-used, never overwritten (losing the signing key would force every
 shop PC to reinstall the CMS by hand).

 Usage (PowerShell, from the repository folder):
   powershell -ExecutionPolicy Bypass -File infrastructure\scripts\setup-github-secrets.ps1 -VpsHost 203.0.113.10
 Optional: -Domain mus-luxury.com  -Repo kairo192/mux-Luxury-  -DeployUser luxe
=============================================================================
#>
param(
  [string]$VpsHost = "",
  [string]$Domain = "mus-luxury.com",
  [string]$Repo = "kairo192/mux-Luxury-",
  [string]$DeployUser = "luxe"
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$tauriDir = Join-Path $HOME ".tauri"
$signKey = Join-Path $tauriDir "mux_luxury.key"
$signPub = "$signKey.pub"
$signPass = Join-Path $tauriDir "mux_luxury.key.password"
$sshDir = Join-Path $HOME ".ssh"
$deployKey = Join-Path $sshDir "mus_luxury_deploy"

function Step($t) { Write-Host "`n== $t" -ForegroundColor Yellow }
function Ok($t) { Write-Host "   OK  $t" -ForegroundColor Green }
function Warn($t) { Write-Host "   !!  $t" -ForegroundColor Red }
# A failed native command (gh) does not stop the script by itself: check each one.
function Assert-Stored($what) {
  if ($LASTEXITCODE -ne 0) { throw "GitHub did not store $what (gh exit code $LASTEXITCODE). Nothing secret was printed; fix the cause and re-run." }
}

function Restrict-ToCurrentUser($path) {
  # Remove inherited permissions: only the current Windows user can read it.
  icacls $path /inheritance:r /grant:r "$($env:USERNAME):(R,W)" | Out-Null
}

function New-StrongPassword {
  $bytes = New-Object byte[] 36
  [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
  return ([Convert]::ToBase64String($bytes) -replace '[+/=]', 'x')
}

# ----------------------------------------------------------------- 1. Tauri
Step "1/4  App-update signing key"
New-Item -ItemType Directory -Force -Path $tauriDir | Out-Null
$repoPub = Join-Path $root "apps\desktop-cms\src-tauri\updater-key.pub"
$storeTauri = $true
if ((Test-Path $signKey) -and (Test-Path $signPass)) {
  if ((Test-Path $repoPub) -and (Test-Path $signPub) -and
      ((Get-Content $signPub -Raw).Trim() -ne (Get-Content $repoPub -Raw).Trim())) {
    throw "The key in $tauriDir does not match apps\desktop-cms\src-tauri\updater-key.pub. Use the key file you received (installed apps only accept that one)."
  }
  Ok "existing key re-used: $signKey"
} elseif (Test-Path $signKey) {
  throw "A signing key exists at $signKey but its password file $signPass is missing. Restore the password file instead of creating a new key."
} elseif (Test-Path $repoPub) {
  # The key pair already exists (public half committed). Do not create another.
  $storeTauri = $false
  Warn "No private signing key in $tauriDir: the TAURI_* secrets are left as they are in GitHub."
  Warn "If they are not set yet, copy the key file you received to $signKey and its password to $signPass, then re-run."
} else {
  $pw = New-StrongPassword
  Push-Location (Join-Path $root "apps\desktop-cms")
  try {
    npx --yes tauri signer generate -w "$signKey" -p "$pw" --ci | Out-Null
  } finally { Pop-Location }
  Set-Content -Path $signPass -Value $pw -NoNewline -Encoding ascii
  Restrict-ToCurrentUser $signKey
  Restrict-ToCurrentUser $signPass
  Copy-Item $signPub $repoPub
  Ok "created $signKey (+ password file, readable only by $($env:USERNAME)); commit $repoPub"
}

# ------------------------------------------------------------- 2. SSH key
Step "2/4  Deploy SSH key (GitHub Actions -> VPS)"
New-Item -ItemType Directory -Force -Path $sshDir | Out-Null
if (Test-Path $deployKey) {
  Ok "existing deploy key re-used: $deployKey"
} else {
  # Through cmd.exe so the EMPTY passphrase (-N "") is passed the same way on
  # Windows PowerShell 5.1 and PowerShell 7 (GitHub Actions needs it unlocked).
  & cmd /c ('ssh-keygen -q -t ed25519 -N "" -C "github-actions-deploy@{0}" -f "{1}"' -f $Domain, $deployKey)
  & cmd /c ('ssh-keygen -y -P "" -f "{0}" >nul 2>&1' -f $deployKey)
  if ($LASTEXITCODE -ne 0) { throw "The deploy key was created with a passphrase; delete $deployKey* and re-run." }
  Restrict-ToCurrentUser $deployKey
  Ok "created $deployKey"
}

# ----------------------------------------------------------- 3. GitHub
Step "3/4  Store in GitHub ($Repo)"
$gh = Get-Command gh -ErrorAction SilentlyContinue
$ghReady = $false
if ($gh) { gh auth status 2>$null | Out-Null; $ghReady = ($LASTEXITCODE -eq 0) }
if ($ghReady) {
  if ($storeTauri) {
    Get-Content $signKey -Raw | gh secret set TAURI_SIGNING_PRIVATE_KEY --repo $Repo
    Assert-Stored TAURI_SIGNING_PRIVATE_KEY
    Get-Content $signPass -Raw | gh secret set TAURI_SIGNING_PRIVATE_KEY_PASSWORD --repo $Repo
    Assert-Stored TAURI_SIGNING_PRIVATE_KEY_PASSWORD
  }
  Get-Content $deployKey -Raw | gh secret set PRODUCTION_SSH_PRIVATE_KEY --repo $Repo
  Assert-Stored PRODUCTION_SSH_PRIVATE_KEY
  gh secret set PRODUCTION_SSH_USER --repo $Repo --body $DeployUser
  Assert-Stored PRODUCTION_SSH_USER
  gh variable set PRODUCTION_URL --repo $Repo --body "https://$Domain"
  Assert-Stored PRODUCTION_URL
  gh variable set PRODUCTION_HEALTH_URL --repo $Repo --body "https://api.$Domain/api/v1/health"
  Assert-Stored PRODUCTION_HEALTH_URL
  if ($VpsHost) {
    gh secret set PRODUCTION_SSH_HOST --repo $Repo --body $VpsHost
    Assert-Stored PRODUCTION_SSH_HOST
    Ok "all secrets and variables stored (VPS host: $VpsHost)"
  } else {
    Warn "PRODUCTION_SSH_HOST not set: re-run with -VpsHost <IP of your VPS> once you have it."
  }
} else {
  Warn "GitHub CLI not ready. Install it (winget install GitHub.cli), run 'gh auth login', then run this script again."
  Warn "Nothing secret was printed; the keys are waiting in $tauriDir and $sshDir."
}

# ----------------------------------------------------------- 4. VPS line
Step "4/4  Give this PUBLIC key to the VPS (safe to share)"
$pubLine = (Get-Content "$deployKey.pub" -Raw).Trim()
Write-Host "   On the VPS, as root:" -ForegroundColor Cyan
Write-Host "   DEPLOY_PUBLIC_KEY='$pubLine' bash infrastructure/scripts/vps-bootstrap.sh"
Write-Host ""
Write-Host "Back up these two files OFF this PC (USB key in a safe):" -ForegroundColor Yellow
Write-Host "   $signKey"
Write-Host "   $signPass"
Write-Host "Losing them means shop PCs can no longer auto-update."
