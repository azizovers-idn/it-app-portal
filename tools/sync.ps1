# -*- coding: utf-8 -*-
<#
.SYNOPSIS
    Simpan semua perubahan lalu kirim ke GitHub dalam satu perintah.

.EXAMPLE
    .\tools\sync.ps1 "tambah aplikasi VPN"
    .\tools\sync.ps1 "perbaiki warna badge status" -NoPush
#>
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Message,

    [switch]$NoPush
)

$ErrorActionPreference = "Stop"

# Pastikan dijalankan dari root repo
$repoRoot = git rev-parse --show-toplevel
Set-Location $repoRoot

git add -A

# Kalau tidak ada perubahan, hentikan tanpa error
if (-not (git status --porcelain)) {
    Write-Host "[sync] Tidak ada perubahan untuk di-commit." -ForegroundColor Yellow
    return
}

git commit -m $Message

if (-not $NoPush) {
    git push
    Write-Host "[sync] ✔ Sudah tersimpan & terkirim ke GitHub." -ForegroundColor Green
} else {
    Write-Host "[sync] ✔ Commit dibuat lokal (push dilewati)." -ForegroundColor Green
}
