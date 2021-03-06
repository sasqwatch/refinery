param(
  [switch] $wheel = $False,
  [string] [ValidateNotNullOrEmpty()] $venv = 'venv'
)

$venv = Convert-Path $venv;

try {
    & (Join-Path $venv 'Scripts\Activate.ps1')
    $activated = $?
} catch {
    $activated = $false
}
if ($activated) {
    Write-Output('-- updating and installing required packages.');
    python -m pip install --upgrade pip
    pip uninstall -y --quiet binary-refinery 
    if ($wheel) {
        Write-Output('-- installing requiements before wheel construction')
        pip install @(Get-Content .\requirements.txt | ForEach-Object {
            if ($_ -eq 'python-magic') {$_ + '-win64'} else {$_}})
        Write-Output('-- building wheel')
        Remove-Item -Recurse dist -ErrorAction SilentlyContinue
        pip install wheel
        python setup.py sdist bdist_wheel 2>&1 | Out-Null
        $wfile = (Get-Item .\dist\*.whl).FullName
        Remove-Item -Recurse binary_refinery.egg-info -ErrorAction SilentlyContinue
        Write-Output("-- installing refinery from wheel: $wfile")
        pip install "$wfile"
    } else {
        pip install -e "$PSScriptRoot"
    }
    deactivate -nondestructive
} else {
    Write-Output('-- error activating virtual environment, please run setup-venv.py');
    exit
}

$refinery = Join-Path $venv 'Scripts';
$refinery = Join-Path $refinery '';

$update = $True;

try {
    $path = (Get-Item HKCU:Environment).GetValue('PATH').split(';')
} catch {
    Write-Output('-- error determining user path variable');
    exit
}

foreach ($item in $path) {
    try {
        if ($refinery -eq (Join-Path ([System.IO.Path]::GetFullPath($item)) '')) {
            $update = $False;
            Write-Output('-- scripts directory already in global path');
            break;
        }
    } catch {}
}
if ($update) {
    $path = ($path + $refinery) -join ';';
    Write-Output('-- adding directory to path: {0}' -f ($refinery));
    $mode = [System.EnvironmentVariableTarget]::User;
    [Environment]::SetEnvironmentVariable('PATH', $path, $mode);
}
