# No installs, services, registry writes, or administrator rights required.
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '../scripts/install_version_policy.ps1')
$cases = @(
    @($null, '4.87.0', 'install'),
    @('Docker Desktop 4.86.9', '4.87.0', 'upgrade'),
    @('Docker Desktop 4.87.0', '4.87.0', 'keep'),
    @('Docker Desktop 4.100.0', '4.87.0', 'keep'),
    @('VS Code 1.99.0', '1.143.0', 'upgrade'),
    @('VS Code 1.143.0', '1.143.0', 'keep'),
    @('VS Code 1.144.0', '1.143.0', 'keep'),
    @('v22.16.0', '24.16.0', 'upgrade'),
    @('v24.16.0', '24.16.0', 'keep'),
    @('v25.0.0', '24.16.0', 'keep'),
    @('git version 2.53.0.windows.1', '2.54.0', 'upgrade'),
    @('git version 2.54.0.windows.1', '2.54.0', 'keep'),
    @('git version 2.55.0.windows.1', '2.54.0', 'keep')
)
foreach ($case in $cases) {
    $actual = Get-InstallAction $case[0] $case[1]
    if ($actual -ne $case[2]) { throw "Wrong action: $($case[0]): $actual" }
}
$rejected = $false
try { Get-InstallAction 'unknown' '4.87.0' | Out-Null } catch { $rejected = $true }
if (-not $rejected) { throw 'Unknown installed version must not trigger an install' }

# Load only function definitions from the real installer; never execute its body.
$tokens = $null; $errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    (Join-Path $PSScriptRoot '../scripts/install_windows.ps1'), [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw ($errors | Out-String) }
foreach ($name in @('Ensure-Minimum', 'Install-Winget')) {
    $fn = $ast.Find({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name }, $true)
    Invoke-Expression $fn.Extent.Text
}
function Say { param($text, $color) }
function Refresh-Path { }
function Resolve-WingetExecutable { 'winget' }
function Record($name, $state, $note) { $script:recorded = $state }
function winget {
    $script:calls += 1
    $script:action = $args[0]
    if ($script:simulateSuccess) { $script:installed = 'v24.16.0' }
    $global:LASTEXITCODE = 0
}
foreach ($scenario in @(
    @($null, $true, 'install', 'install'),
    @('v22.0.0', $true, 'upgrade', 'upgrade'),
    @('v24.16.0', $true, 'none', 'keep'),
    @('v25.0.0', $true, 'none', 'keep'),
    @('v22.0.0', $false, 'upgrade', 'fail'),
    @('unknown', $true, 'none', 'fail')
)) {
    $script:installed = $scenario[0]; $script:simulateSuccess = $scenario[1]
    $script:calls = 0; $script:action = 'none'; $script:recorded = ''
    Ensure-Minimum 'Node.js' 'OpenJS.NodeJS' '24.16.0' { $script:installed }
    if ($script:action -ne $scenario[2]) { throw 'Wrong winget action' }
    if ($scenario[2] -eq 'none' -and $script:calls -ne 0) { throw 'Unexpected installation' }
    # Compare against a captured failure rather than depending on console encoding.
    if ($scenario[3] -eq 'fail') { $failureState = $script:recorded }
    elseif ($failureState -and $script:recorded -eq $failureState) { throw 'Unexpected failure' }
    if ($scenario[3] -eq 'fail' -and $script:recorded -notmatch ([char]0xC2E4).ToString()) { throw 'Failed verification reported success' }
}
Write-Host 'PASS: 14 version cases and 6 installer scenarios; no installation performed.'
