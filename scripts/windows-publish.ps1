param(
    [string]$RepoPath = "C:\Users\wyl26\auto-maintainer"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path (Join-Path $RepoPath ".git"))) {
    throw "Repository not found at $RepoPath"
}

Push-Location $RepoPath
try {
    python -m pytest -q

    $status = git status --short
    if ($status) {
        Write-Host "Uncommitted changes detected:"
        $status
        throw "Commit changes before publishing."
    }

    git fetch origin
    git push origin main
    gh run list --repo wyl2607/auto-maintainer --branch main --limit 3 --json databaseId,name,status,conclusion,url
} finally {
    Pop-Location
}
