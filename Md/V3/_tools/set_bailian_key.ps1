$ErrorActionPreference = 'Stop'
$secureKey = Read-Host 'Enter DASHSCOPE_API_KEY (hidden input)' -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)

try {
    $apiKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    if ([string]::IsNullOrWhiteSpace($apiKey)) {
        throw 'No DASHSCOPE_API_KEY was entered.'
    }
    [Environment]::SetEnvironmentVariable('DASHSCOPE_API_KEY', $apiKey, 'User')
    Write-Output 'DASHSCOPE_API_KEY saved for the current Windows user.'
}
finally {
    $apiKey = $null
    if ($bstr -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}
