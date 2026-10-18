$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [System.Environment]::GetFolderPath('Desktop')
$ShortcutPath = Join-Path $DesktopPath "TikTok Buffer Automator.lnk"

# Caminho para o executavel compilado
$TargetPath = "C:\Users\leurickkkk77\.gemini\antigravity\scratch\tiktok-buffer-automator\dist\TikTokBufferAutomator\TikTokBufferAutomator.exe"
$WorkingDir = "C:\Users\leurickkkk77\.gemini\antigravity\scratch\tiktok-buffer-automator\dist\TikTokBufferAutomator"

# Se o exe ainda nao existir, aponta para o iniciar.bat
if (-not (Test-Path $TargetPath)) {
    $TargetPath = "C:\Users\leurickkkk77\.gemini\antigravity\scratch\tiktok-buffer-automator\iniciar.bat"
    $WorkingDir = "C:\Users\leurickkkk77\.gemini\antigravity\scratch\tiktok-buffer-automator"
}

$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $TargetPath
$Shortcut.WorkingDirectory = $WorkingDir
$Shortcut.Description = "TikTok Buffer Automator Pro"
$Shortcut.Save()

Write-Host "Atalho criado na Area de Trabalho com sucesso: $ShortcutPath"
