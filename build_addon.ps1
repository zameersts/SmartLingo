$src = 'c:\my\SmartLingo'
$out = 'c:\my\SmartLingo\SmartLingo-1.5.nvda-addon'

# Agar purani file hai to delete karo
if (Test-Path $out) { Remove-Item $out -Force }

Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::Open($out, 'Create')

# In items ko include karna hai
$include = @('manifest.ini', 'globalPlugins', 'lib', 'doc')

foreach ($item in $include) {
    $fullPath = Join-Path $src $item
    if (Test-Path $fullPath -PathType Leaf) {
        [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $fullPath, $item) | Out-Null
        Write-Host "Added file: $item"
    } elseif (Test-Path $fullPath -PathType Container) {
        Get-ChildItem -Path $fullPath -Recurse -File | ForEach-Object {
            $relativePath = $_.FullName.Substring($src.Length + 1).Replace('\', '/')
            # __pycache__ skip karo
            if ($relativePath -notlike '*__pycache__*' -and $relativePath -notlike '*.pyc') {
                [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $_.FullName, $relativePath) | Out-Null
                Write-Host "Added: $relativePath"
            }
        }
    }
}

$zip.Dispose()
$sizeKB = [math]::Round((Get-Item $out).Length / 1KB, 2)
Write-Host ""
Write-Host "=== BUILD COMPLETE ==="
Write-Host "File: $out"
Write-Host "Size: $sizeKB KB"
