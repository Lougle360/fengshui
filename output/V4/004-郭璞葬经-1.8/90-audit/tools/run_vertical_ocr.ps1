param(
    [int]$FirstPage = 1,
    [int]$LastPage = 29
)

$ErrorActionPreference = 'Stop'
$Workspace = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$PdfPath = Join-Path $Workspace '00-intake\source.pdf'
$ReviewImageDir = Join-Path $Workspace '90-audit\review-images'
$OcrDir = Join-Path $Workspace '90-audit\ocr-v19b'
$ModelDir = Join-Path $Workspace '90-audit\ocr-models'
$PdfToPpm = 'D:\CDriveMigration\QIQI-cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin\pdftoppm.exe'
$Tesseract = 'C:\Program Files\Tesseract-OCR\tesseract.exe'

New-Item -ItemType Directory -Force -Path $ReviewImageDir, $OcrDir | Out-Null

$Panels = @(
    @{ Name = 'top-right'; X = 640; Y = 150; W = 600; H = 850 },
    @{ Name = 'top-left'; X = 70; Y = 150; W = 580; H = 850 },
    @{ Name = 'bottom-right'; X = 640; Y = 980; W = 600; H = 850 },
    @{ Name = 'bottom-left'; X = 70; Y = 980; W = 580; H = 850 }
)

for ($Page = $FirstPage; $Page -le $LastPage; $Page++) {
    $PageId = 'P{0:D6}' -f $Page
    foreach ($Panel in $Panels) {
        $BaseName = "$PageId-$($Panel.Name)"
        $CropBase = Join-Path $ReviewImageDir $BaseName
        $CropPath = "$CropBase.jpg"
        $OcrBase = Join-Path $OcrDir $BaseName
        $OcrPath = "$OcrBase.txt"
        if (-not (Test-Path -LiteralPath $CropPath)) {
            & $PdfToPpm -f $Page -l $Page -r 400 -x $Panel.X -y $Panel.Y -W $Panel.W -H $Panel.H -jpeg -singlefile $PdfPath $CropBase
            if ($LASTEXITCODE -ne 0) { throw "pdftoppm failed: $BaseName" }
        }
        if (-not (Test-Path -LiteralPath $OcrPath)) {
            & $Tesseract $CropPath $OcrBase --tessdata-dir $ModelDir -l chi_tra_vert --oem 1 --psm 5 2>$null
            if ($LASTEXITCODE -ne 0) { throw "tesseract failed: $BaseName" }
        }
    }
    Write-Output "$PageId complete"
}
