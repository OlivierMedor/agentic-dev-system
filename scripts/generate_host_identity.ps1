param (
    [string]$ProjectRoot = ".",
    [string]$BaseRef = "origin/main",
    [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"

try {
    # 1. Resolve project root path and ensure it's absolute
    $resolvedRoot = (Get-Item $ProjectRoot).FullName

    # Ensure we are inside a git repository
    Set-Location $resolvedRoot
    $gitCheck = git rev-parse --is-inside-work-tree 2>$null
    if ($LASTEXITCODE -ne 0 -or $gitCheck -ne "true") {
        throw "Not a git repository: $resolvedRoot"
    }

    # 2. Get git parameters
    $branchRaw = git branch --show-current
    if ($null -eq $branchRaw) {
        $branch = ""
    } else {
        $branch = ([string]$branchRaw).Trim()
    }
    $headSha = (git rev-parse HEAD).Trim()
    $gitDir = (git rev-parse --git-dir).Trim()
    $shallowRepo = (git rev-parse --is-shallow-repository).Trim()
    $shallowClone = ($shallowRepo -eq "true")
    $detachedHead = [string]::IsNullOrEmpty($branch)

    # Resolve base SHA
    $baseSha = (git rev-parse --verify $BaseRef).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "Base ref '$BaseRef' could not be resolved."
    }

    # Resolve merge-base SHA
    $mergeBaseSha = (git merge-base HEAD $BaseRef).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "Could not find a merge base between HEAD and '$BaseRef'."
    }

    # Resolve remote origin URL
    $remoteUrlRaw = (git config --get remote.origin.url).Trim()
    if ($LASTEXITCODE -ne 0) {
        $remoteUrlRaw = $null
    }

    # Helper to strip credentials/tokens/secrets from remote url before writing
    function Strip-Credentials {
        param (
            [string]$url
        )
        if ([string]::IsNullOrEmpty($url)) { return $null }
        $url = ($url -split '#', 2)[0]
        $url = ($url -split '\?', 2)[0]
        if ($url -match "^([a-zA-Z0-9+-]+)://([^@/]+)@(.*)$") {
            return "${Matches[1]}://${Matches[3]}"
        }
        return $url
    }

    $remoteUrl = Strip-Credentials $remoteUrlRaw

    # Resolve root commits
    $rootCommitsOutput = (git rev-list --max-parents=0 HEAD).Trim()
    $rootCommitShas = @()
    if ($LASTEXITCODE -eq 0 -and ![string]::IsNullOrEmpty($rootCommitsOutput)) {
        $rootCommitShas = $rootCommitsOutput -split "`r`n"
        $rootCommitShas = $rootCommitShas | ForEach-Object { $_.Trim() } | Where-Object { ![string]::IsNullOrEmpty($_) }
        $rootCommitShas = $rootCommitShas | Sort-Object
    }

    # 3. Canonical remote normalization in PowerShell
    function Normalize-GitUrl {
        param (
            [string]$url
        )
        if ([string]::IsNullOrEmpty($url)) { return $null }
        $url = $url.Trim()
        
        # Remove fragments and query parameters
        $url = ($url -split '#', 2)[0]
        $url = ($url -split '\?', 2)[0]
        
        # Local path checks
        if ($url -match "^[a-zA-Z]:" -or $url.StartsWith("/") -or $url.StartsWith("\") -or $url.StartsWith("file://") -or $url.StartsWith("localhost") -or $url.StartsWith("127.0.0.1")) {
            return $null
        }
        
        $hostName = ""
        $path = ""
        
        # Check for SCP-style SSH: e.g. git@github.com:owner/repo.git
        if ($url -match "^([^@/]+)@([^:/]+):([^/].*)$" -and $url -notlike "*://*") {
            $hostName = $Matches[2]
            $path = $Matches[3]
        } else {
            # Standard URL parse
            $urlNoProto = $url
            if ($url -match "^([a-zA-Z0-9+-]+)://") {
                $urlNoProto = $url -replace "^([a-zA-Z0-9+-]+)://", ""
            }
            
            # Strip credentials before @
            if ($urlNoProto -like "*@*") {
                $urlNoProto = ($urlNoProto -split "@", 2)[1]
            }
            
            # Split host and path
            if ($urlNoProto -like "*/*") {
                $parts = $urlNoProto -split "/", 2
                $hostPort = $parts[0]
                $path = $parts[1]
            } else {
                $hostPort = $urlNoProto
                $path = ""
            }
            
            # Strip port
            $hostName = ($hostPort -split ":", 2)[0]
        }
        
        if ($null -eq $hostName) {
            $hostName = ""
        }
        if ($null -eq $path) {
            $path = ""
        }

        # Lowercase host
        $hostName = $hostName.ToLower()
        if ($hostName -eq "github.com" -or $hostName -eq "ssh.github.com") {
            $hostName = "github.com"
        }
        
        # Replace backslashes
        $path = $path.Replace("\", "/")
        # Remove redundant slashes
        while ($path -like "*//*") {
            $path = $path.Replace("//", "/")
        }
        $path = $path.Trim('/')
        
        # Strip trailing .git
        if ($path.ToLower().EndsWith(".git")) {
            $path = $path.Substring(0, $path.Length - 4)
        }
        
        # Casing normalization for known hosts
        $knownHosts = @("github.com", "gitlab.com", "bitbucket.org")
        if ($knownHosts -contains $hostName) {
            $path = $path.ToLower()
        }
        
        if ([string]::IsNullOrEmpty($hostName)) {
            return $null
        }
        
        return "${hostName}/${path}"
    }

    $normalizedRemoteUrl = Normalize-GitUrl $remoteUrl

    # 4. Determine repository_id, strength, version
    $repositoryId = $null
    $repositoryIdStrength = "none"
    $repositoryIdVersion = $null

    if ($rootCommitShas.Length -gt 0 -and ![string]::IsNullOrEmpty($normalizedRemoteUrl)) {
        # Build canonical payload:
        # repository-id-v1
        # <sorted-root-commit-list>
        # <normalized-remote-url>
        $lines = @("repository-id-v1") + $rootCommitShas + @($normalizedRemoteUrl)
        $payload = $lines -join "`n"
        
        # Compute SHA-256 hash using .NET
        $hasher = [System.Security.Cryptography.SHA256]::Create()
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($payload)
        $hashBytes = $hasher.ComputeHash($bytes)
        $repositoryId = [System.BitConverter]::ToString($hashBytes).Replace("-", "").ToLower()
        $repositoryIdStrength = "strong"
        $repositoryIdVersion = 1
    } elseif ($rootCommitShas.Length -gt 0) {
        $repositoryId = $rootCommitShas[0]
        $repositoryIdStrength = "weak"
    } elseif (![string]::IsNullOrEmpty($normalizedRemoteUrl)) {
        $repositoryId = $normalizedRemoteUrl
        $repositoryIdStrength = "none"
    }

    # 5. Build identity hash
    # Handle root_commit_shas array serialization safely
    $rootCommitShasJson = @()
    foreach ($sha in $rootCommitShas) {
        $rootCommitShasJson += $sha
    }

    $identity = [ordered]@{
        "root"                   = $resolvedRoot
        "branch"                 = $branch
        "head_sha"               = $headSha
        "requested_base_ref"     = $BaseRef
        "base_sha"               = $baseSha
        "merge_base_sha"         = $mergeBaseSha
        "git_dir"                = $gitDir
        "detached_head"          = $detachedHead
        "shallow_clone"          = $shallowClone
        "remote_url"             = $remoteUrl
        "normalized_remote_url"  = $normalizedRemoteUrl
        "root_commit_shas"       = $rootCommitShasJson
        "repository_id"          = $repositoryId
        "repository_id_strength" = $repositoryIdStrength
        "repository_id_version"  = $repositoryIdVersion
    }

    # 6. Convert to JSON and save
    $json = ConvertTo-Json -InputObject $identity -Depth 5
    if ([string]::IsNullOrEmpty($OutputPath)) {
        $OutputPath = Join-Path $resolvedRoot "host_identity.json"
    }
    
    # Ensure OutputPath parent folder exists
    $parent = Split-Path $OutputPath
    if (![string]::IsNullOrEmpty($parent) -and !(Test-Path $parent)) {
        New-Item -ItemType Directory -Force -Path $parent > $null
    }

    [System.IO.File]::WriteAllText($OutputPath, $json, [System.Text.Encoding]::UTF8)
    Write-Output "Host identity successfully written to: $OutputPath"
} catch {
    Write-Error "Failed to generate host identity: $_"
    exit 1
}
