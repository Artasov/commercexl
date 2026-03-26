param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("patch", "minor", "major")]
    [string]$Part,

    [switch]$Push,
    [switch]$DryRun
)

$arguments = @("run", "python", "scripts/release.py", $Part)
if ($Push) { $arguments += "--push" }
if ($DryRun) { $arguments += "--dry-run" }

uv @arguments
