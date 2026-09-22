$ErrorActionPreference='Stop'
$base=$PSScriptRoot
Add-Type -AssemblyName System.Windows.Forms
try {
    $statePath=Join-Path $base 'install-state.json'
    if (!(Test-Path -LiteralPath $statePath)) { throw 'Registrazione installazione assente: nessun file rimosso.' }
    $state=Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($state.product -ne 'MetinHub' -or [IO.Path]::GetFullPath($state.path) -ne [IO.Path]::GetFullPath($base)) {
        throw 'La cartella non corrisponde alla registrazione MetinHub.'
    }
    $running=Get-CimInstance Win32_Process | Where-Object {
        ($_.ExecutablePath -eq (Join-Path $base 'MetinHub.exe')) -or
        ($_.Name -match '^pythonw?\.exe$' -and $_.CommandLine -like '*osserva_metin.py*' -and $_.ExecutablePath -like "$base\*")
    }
    if ($running) { throw 'Chiudi MetinHub prima di disinstallare.' }
    $answer=[Windows.Forms.MessageBox]::Show('Rimuovere MetinHub, i collegamenti e il suo ambiente .venv? Impostazioni, registri, backup, Python e runtime condivisi saranno conservati.','Disinstalla MetinHub','YesNo','Question')
    if ($answer -ne 'Yes') { exit }
    $allowed=@('configurazione.py','supporto_core.py','supporto_worker.py','supporto_input.py','supporto_mana.py','supporto_abilita.py','supporto_ui.py','SUPPORTO_LEGGIMI.txt','VERSION.txt','README.md','CHANGELOG.md','osserva_metin.py','cattura_metin.py','riconosci_scheggia.py','seleziona_area.py','manutenzione_metin.py','interfaccia_sistema.py','setup_check.py','Installa_MetinHub.ps1','Installa_MetinHub.bat','Avvia_MetinHub.bat','MetinHub.exe','MetinHub.ico','MetinHub.png','MetinHub.svg','MetinHub_Launcher.cs','MetinHub.manifest','requirements-cpu.txt','constraints.txt','LEGGIMI.txt','DISTRIBUZIONE.txt','crea_manifest.py','pesca_contatore.json','pesca_input.py','tema_metin.py','panorama_metin.png','ASPETTO_LEGGIMI.txt','pesca_core.py','pesca_debug.py','pesca_riferimento.png','PESCA_LEGGIMI.txt','Disinstalla_MetinHub.ps1')
    foreach ($name in $state.files) {
        if ($name -notin $allowed) { throw ('Nome inatteso nella registrazione: '+$name) }
    }
    $shell=New-Object -ComObject WScript.Shell
    foreach ($folder in @([Environment]::GetFolderPath('Desktop'),[Environment]::GetFolderPath('Programs'))) {
        $file=Join-Path $folder 'MetinHub.lnk'
        if (Test-Path -LiteralPath $file) {
            $link=$shell.CreateShortcut($file)
            if ($link.TargetPath -eq (Join-Path $base 'MetinHub.exe')) { Remove-Item -LiteralPath $file -Force }
        }
    }
    $envPath=Join-Path $base '.venv'
    if (Test-Path -LiteralPath (Join-Path $envPath 'pyvenv.cfg')) {
        $item=Get-Item -LiteralPath $envPath -Force
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Ambiente collegato a un’altra cartella: non rimosso.' }
        Remove-Item -LiteralPath $envPath -Recurse -Force
    }
    foreach ($name in $state.files) {
        $file=Join-Path $base $name
        if (Test-Path -LiteralPath $file -PathType Leaf) { Remove-Item -LiteralPath $file -Force }
    }
    Remove-Item -LiteralPath $statePath -Force
    Remove-Item 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\MetinHub' -Force -ErrorAction SilentlyContinue
    [void][Windows.Forms.MessageBox]::Show('MetinHub rimosso. Dati personali e componenti condivisi conservati nella cartella originale.','MetinHub')
} catch { [void][Windows.Forms.MessageBox]::Show($_.Exception.Message,'Disinstallazione non completata'); exit 1 }
