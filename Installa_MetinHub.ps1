param([switch]$Worker)
$ErrorActionPreference = 'Stop'
$base = $PSScriptRoot
$appVersion = (Get-Content -LiteralPath (Join-Path $base 'VERSION.txt') -Raw).Trim()
if ($appVersion -notmatch '^\d+\.\d+\.\d+$') { throw 'VERSION.txt non valido.' }
$log = Join-Path $base 'installazione_log.txt'
function Log([string]$text) {
    Add-Content -LiteralPath $log -Value (('{0:HH:mm:ss} | ' -f (Get-Date)) + $text) -Encoding UTF8
}
function Run-Tool([string]$file, [string[]]$arguments) {
    Log ('Esecuzione: ' + [IO.Path]::GetFileName($file) + ' ' + ($arguments -join ' '))
    $old = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { & $file @arguments 2>&1 | ForEach-Object { Log ([string]$_) }; $code=$LASTEXITCODE }
    finally { $ErrorActionPreference=$old }
    if ($code -ne 0) { throw ('Comando non riuscito, codice ' + $code + '. Vedi installazione_log.txt.') }
}
function Test-Python([string]$file, [string]$mode) {
    if (!(Test-Path -LiteralPath $file -PathType Leaf)) { return $false }
    $old=$ErrorActionPreference; $ErrorActionPreference='Continue'
    try {
        & $file (Join-Path $base 'setup_check.py') $mode 2>&1 | ForEach-Object { Log ([string]$_) }
        return ($LASTEXITCODE -eq 0)
    } finally { $ErrorActionPreference=$old }
}
function Download([string]$url, [string]$file) {
    [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $url -OutFile $file -UseBasicParsing -TimeoutSec 180
}
if ($Worker) {
    try {
        Set-Content -LiteralPath $log -Value ('MetinHub '+$appVersion+' - installazione e verifica') -Encoding UTF8
        if (![Environment]::Is64BitOperatingSystem -or $env:PROCESSOR_ARCHITECTURE -eq 'ARM64') {
            throw 'Questo pacchetto richiede Windows 10/11 x64 Intel o AMD.'
        }
        Log '1/6 - Controllo componenti Windows.'
        $vc=Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64' -ErrorAction SilentlyContinue
        if (!$vc -or $vc.Installed -ne 1) {
            Log 'Installazione runtime Microsoft Visual C++. Potrebbe apparire la conferma di Windows.'
            $redist=Join-Path $env:TEMP ('MetinHub-vc-' + [guid]::NewGuid().ToString() + '.exe')
            Download 'https://aka.ms/vs/17/release/vc_redist.x64.exe' $redist
            $sig=Get-AuthenticodeSignature -LiteralPath $redist
            if ($sig.Status -ne 'Valid' -or $sig.SignerCertificate.Subject -notmatch 'Microsoft Corporation') { throw 'Firma del runtime Microsoft non valida.' }
            $proc=Start-Process -FilePath $redist -ArgumentList '/install /passive /norestart' -Verb RunAs -Wait -PassThru
            if ($proc.ExitCode -notin @(0,1638,3010)) { throw ('Runtime Microsoft: errore ' + $proc.ExitCode) }
            Remove-Item -LiteralPath $redist -Force
            if ($proc.ExitCode -eq 3010) { Log 'Il runtime richiede un riavvio Windows: se la verifica finale fallisce, riavvia e ripeti.' }
        } else { Log 'Runtime Microsoft gia presente.' }
        Log '2/6 - Controllo Python e ambiente del progetto.'
        $venv=Join-Path $base '.venv\Scripts\python.exe'
        if (!(Test-Python $venv 'python')) {
            $python=$null
            $py=Get-Command py.exe -ErrorAction SilentlyContinue
            if ($py) {
                foreach ($version in @('-3.13','-3.12','-3.14')) {
                    $old=$ErrorActionPreference; $ErrorActionPreference='Continue'
                    $found=& $py.Source $version -c 'import sys; print(sys.executable)' 2>$null
                    $ok=$LASTEXITCODE -eq 0
                    $ErrorActionPreference=$old
                    if ($ok -and $found -and (Test-Python ([string]($found | Select-Object -Last 1)) 'python')) {
                        $python=[string]($found | Select-Object -Last 1); break
                    }
                }
            }
            if (!$python) {
                foreach ($hive in @('HKCU','HKLM')) {
                    foreach ($version in @('3.13','3.12','3.14')) {
                        $key=$hive+':\SOFTWARE\Python\PythonCore\'+$version+'\InstallPath'
                        $registered=Get-ItemProperty -LiteralPath $key -ErrorAction SilentlyContinue
                        if ($registered -and $registered.ExecutablePath -and (Test-Python $registered.ExecutablePath 'python')) {
                            $python=$registered.ExecutablePath; break
                        }
                    }
                    if ($python) { break }
                }
            }
            $private=Join-Path $base '.runtime\python.exe'
            if (!$python -and (Test-Python $private 'python')) { $python=$private }
            if (!$python) {
                Log 'Python compatibile non trovato: download Python 3.13.15 x64 dal sito ufficiale.'
                $installer=Join-Path $env:TEMP ('MetinHub-python-' + [guid]::NewGuid().ToString() + '.exe')
                Download 'https://www.python.org/ftp/python/3.13.15/python-3.13.15-amd64.exe' $installer
                $expected='edec09c4853aeae9ac36efb8c9f95b6b8e2fee65eee56d9767a8b7c69c574403'
                if ((Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) { throw 'Il file Python scaricato non corrisponde alla versione prevista.' }
                $runtime=Join-Path $base '.runtime'
                $arguments='/quiet InstallAllUsers=0 Include_launcher=0 Include_test=0 Include_doc=0 Include_pip=1 Include_tcltk=1 PrependPath=0 Shortcuts=0 TargetDir="' + $runtime + '"'
                $proc=Start-Process -FilePath $installer -ArgumentList $arguments -Wait -PassThru
                if ($proc.ExitCode -notin @(0,3010)) { throw ('Installazione Python: errore ' + $proc.ExitCode) }
                Remove-Item -LiteralPath $installer -Force
                $python=$private
                if (!(Test-Python $python 'python')) { throw 'Python installato ma non avviabile. Vedi il registro.' }
            }
            $oldEnv=Join-Path $base '.venv'
            if (Test-Path -LiteralPath $oldEnv) {
                $backup='.venv_backup_' + (Get-Date -Format 'yyyyMMdd_HHmmss')
                Rename-Item -LiteralPath $oldEnv -NewName $backup
                Log ('Ambiente non avviabile conservato in ' + $backup)
            }
            Run-Tool $python @('-m','venv',(Join-Path $base '.venv'))
        } else { Log 'Ambiente Python gia presente e compatibile.' }
        Log '3/6 - Controllo librerie OCR, immagini e mouse.'
        if (!(Test-Python $venv 'imports')) {
            Log 'Installazione/riparazione librerie nell ambiente del progetto. Download anche di centinaia di MB.'
            Run-Tool $venv @('-m','pip','install','--upgrade','pip','--timeout','30','--retries','2')
            Run-Tool $venv @('-m','pip','install','--force-reinstall','torch==2.9.1','torchvision==0.24.1','--index-url','https://download.pytorch.org/whl/cpu','--timeout','30','--retries','2')
            Run-Tool $venv @('-m','pip','install','-r',(Join-Path $base 'requirements-cpu.txt'),'-c',(Join-Path $base 'constraints.txt'),'--timeout','30','--retries','2')
            if (!(Test-Python $venv 'imports')) { throw 'Verifica librerie fallita. Nessun avvio automatico del programma.' }
        } else { Log 'Librerie gia funzionanti: installazione esistente conservata.' }
        Log 'Controllo HTTPS per il download dei modelli.'
        if (!(Test-Python $venv 'tls')) {
            Run-Tool $venv @('-m','pip','install','truststore==0.10.4','--timeout','30','--retries','2')
            if (!(Test-Python $venv 'tls')) { throw 'Componente HTTPS non avviabile. Vedi installazione_log.txt.' }
        }
        Log '4/6 - Verifica/scaricamento modelli OCR. Il primo download puo richiedere alcuni minuti.'
        Run-Tool $venv @((Join-Path $base 'setup_check.py'),'models')
        Log '5/6 - Creazione avviatore MetinHub.exe con icona.'
        $csc=Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
        if (!(Test-Path -LiteralPath $csc)) { $csc=Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe' }
        if (!(Test-Path -LiteralPath $csc)) { throw 'Compilatore .NET di Windows non trovato. Il programma resta avviabile con Avvia_MetinHub.bat.' }
        $exe=Join-Path $base 'MetinHub.exe'
        # Compilare da file locali a nomi semplici: niente percorsi assoluti
        # dentro gli argomenti /win32manifest e /win32icon del vecchio csc.
        $build=Join-Path ([IO.Path]::GetTempPath()) ('MetinHub-build-'+[guid]::NewGuid().ToString('N'))
        [void](New-Item -ItemType Directory -Path $build)
        try {
            foreach ($entry in @(@('MetinHub_Launcher.cs','launcher.cs'),@('MetinHub.ico','app.ico'))) {
                $source=Join-Path $base $entry[0]
                if (!(Test-Path -LiteralPath $source -PathType Leaf)) { throw ('File necessario assente: '+$source) }
                $bytes=[IO.File]::ReadAllBytes($source)
                if ($bytes.Length -eq 0) { throw ('File necessario vuoto: '+$source) }
                [IO.File]::WriteAllBytes((Join-Path $build $entry[1]),$bytes)
                Log ('File letto: '+$entry[0]+' ('+$bytes.Length+' byte)')
            }
            $launcherFile=Join-Path $build 'launcher.cs'
            $launcherText=[IO.File]::ReadAllText($launcherFile)
            $launcherText=[regex]::Replace($launcherText,'AssemblyVersion\("[0-9.]+"\)',('AssemblyVersion("'+$appVersion+'.0")'))
            [IO.File]::WriteAllText($launcherFile,$launcherText,[Text.Encoding]::UTF8)
            $originalManifest=Join-Path $base 'MetinHub.manifest'
            Log ('Manifesto nella cartella app: esiste='+[IO.File]::Exists($originalManifest))
            # Manifesto dell'avviatore noto, rigenerato senza cambiare privilegi.
            $manifestText=@"
<?xml version="1.0" encoding="utf-8"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">
  <assemblyIdentity version="$appVersion.0" name="MetinHub.Desktop"/>
  <trustInfo xmlns="urn:schemas-microsoft-com:asm.v3"><security><requestedPrivileges>
    <requestedExecutionLevel level="requireAdministrator" uiAccess="false"/>
  </requestedPrivileges></security></trustInfo>
</assembly>
"@
            [IO.File]::WriteAllText((Join-Path $build 'app.manifest'),$manifestText,(New-Object System.Text.UTF8Encoding($false)))
            $xml=New-Object System.Xml.XmlDocument
            $xml.Load((Join-Path $build 'app.manifest'))
            $options=@('/nologo','/target:winexe','/platform:anycpu','/reference:System.Windows.Forms.dll',
                       '/win32icon:app.ico','/win32manifest:app.manifest','/out:MetinHub.exe','launcher.cs')
            [IO.File]::WriteAllLines((Join-Path $build 'build.rsp'),[string[]]$options,[Text.Encoding]::ASCII)
            Log ('Compilatore: '+$csc)
            Log ('Cartella compilazione: '+$build)
            Log ('Manifesto generato e XML verificato: '+(Get-Item -LiteralPath (Join-Path $build 'app.manifest')).Length+' byte; requireAdministrator')
            Push-Location -LiteralPath $build
            try { Run-Tool $csc @('@build.rsp') }
            finally { Pop-Location }
            $builtExe=Join-Path $build 'MetinHub.exe'
            if (!(Test-Path -LiteralPath $builtExe -PathType Leaf)) { throw 'Il compilatore non ha prodotto MetinHub.exe.' }
            Copy-Item -LiteralPath $builtExe -Destination $exe -Force
            Log 'Avviatore compilato e copiato nella cartella MetinHub.'
        } finally {
            if (Test-Path -LiteralPath $build) { Remove-Item -LiteralPath $build -Recurse -Force -ErrorAction SilentlyContinue }
        }
        Log '6/6 - Collegamenti Desktop e menu Start.'
        $shell=New-Object -ComObject WScript.Shell
        foreach ($folder in @([Environment]::GetFolderPath('Desktop'),[Environment]::GetFolderPath('Programs'))) {
            if ($folder) {
                $link=$shell.CreateShortcut((Join-Path $folder 'MetinHub.lnk'))
                $link.TargetPath=$exe; $link.WorkingDirectory=$base; $link.IconLocation=$exe+',0'
                $link.Description='MetinHub - riconoscimento e raccolta'
                $link.Save()
            }
        }
        Log 'Registrazione in App installate di Windows.'
        $key='HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\MetinHub'
        [void](New-Item -Path $key -Force)
        $ps=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
        $uninstall='"'+$ps+'" -NoProfile -ExecutionPolicy Bypass -File "'+(Join-Path $base 'Disinstalla_MetinHub.ps1')+'"'
        foreach ($pair in @{DisplayName='MetinHub';DisplayVersion=$appVersion;Publisher='MetinHub - progetto personale';InstallLocation=$base;DisplayIcon=$exe;UninstallString=$uninstall}.GetEnumerator()) {
            [void](New-ItemProperty -Path $key -Name $pair.Key -Value $pair.Value -PropertyType String -Force)
        }
        [void](New-ItemProperty -Path $key -Name NoModify -Value 1 -PropertyType DWord -Force)
        [void](New-ItemProperty -Path $key -Name NoRepair -Value 1 -PropertyType DWord -Force)
        $owned=@('VERSION.txt','README.md','CHANGELOG.md','osserva_metin.py','cattura_metin.py','riconosci_scheggia.py','seleziona_area.py','manutenzione_metin.py','interfaccia_sistema.py','setup_check.py','Installa_MetinHub.ps1','Installa_MetinHub.bat','Avvia_MetinHub.bat','MetinHub.exe','MetinHub.ico','MetinHub.png','MetinHub.svg','MetinHub_Launcher.cs','MetinHub.manifest','requirements-cpu.txt','constraints.txt','LEGGIMI.txt','DISTRIBUZIONE.txt','crea_manifest.py','pesca_contatore.json','pesca_input.py','tema_metin.py','panorama_metin.png','ASPETTO_LEGGIMI.txt','pesca_core.py','pesca_debug.py','pesca_riferimento.png','PESCA_LEGGIMI.txt','Disinstalla_MetinHub.ps1')
        @{product='MetinHub';version=$appVersion;path=$base;files=$owned} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $base 'install-state.json') -Encoding UTF8
        Log 'COMPLETATO. Apri MetinHub dal Desktop e conferma la richiesta amministratore.'
        return 'SUCCESS'
    } catch {
        Log ('ERRORE: ' + $_.Exception.Message)
        return 'FAILED'
    }
}
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[Windows.Forms.Application]::EnableVisualStyles()
$form=New-Object Windows.Forms.Form
$form.Text='MetinHub - Installazione'; $form.ClientSize=New-Object Drawing.Size(760,540)
$form.StartPosition='CenterScreen'; $form.FormBorderStyle='FixedDialog'; $form.MaximizeBox=$false
$icon=Join-Path $base 'MetinHub.ico'
if (Test-Path -LiteralPath $icon) { $form.Icon=New-Object Drawing.Icon($icon) }
$title=New-Object Windows.Forms.Label
$title.Text='MetinHub | prepara questo PC'; $title.Font=New-Object Drawing.Font('Segoe UI',18,[Drawing.FontStyle]::Bold)
$title.SetBounds(22,18,715,40); $form.Controls.Add($title)
$info=New-Object Windows.Forms.Label
$info.Text="Controlla i componenti presenti e installa quelli mancanti. Servono Internet e spazio per le librerie OCR. L'installazione standard usa la CPU e crea i collegamenti con icona.`r`nCartella: $base"
$info.SetBounds(24,65,705,80);$form.Controls.Add($info)
$output=New-Object Windows.Forms.TextBox
$output.Multiline=$true;$output.ReadOnly=$true;$output.ScrollBars='Vertical';$output.SetBounds(24,155,710,300)
$output.Font=New-Object Drawing.Font('Consolas',9); $form.Controls.Add($output)
$button=New-Object Windows.Forms.Button
$button.Text='Verifica e installa';$button.SetBounds(24,475,190,40);$form.Controls.Add($button)
$status=New-Object Windows.Forms.Label
$status.Text='Premi il pulsante per iniziare.';$status.SetBounds(235,482,490,42);$form.Controls.Add($status)
$script:job=$null
$form.BackColor=[Drawing.ColorTranslator]::FromHtml('#101619')
$form.ForeColor=[Drawing.ColorTranslator]::FromHtml('#eeeae1')
$title.ForeColor=[Drawing.ColorTranslator]::FromHtml('#d7b578')
$output.BackColor=[Drawing.ColorTranslator]::FromHtml('#192125')
$output.ForeColor=$form.ForeColor
$output.BorderStyle='FixedSingle'
$button.FlatStyle='Flat'
$button.BackColor=[Drawing.ColorTranslator]::FromHtml('#d7b578')
$button.ForeColor=[Drawing.ColorTranslator]::FromHtml('#101619')
$button.FlatAppearance.BorderSize=0
$script:setupPath=$PSCommandPath
$button.Add_Click({
    $button.Enabled=$false;$status.Text='Installazione in corso...'
    $script:job=Start-Job -ScriptBlock { param($path) & $path -Worker } -ArgumentList $script:setupPath
})
$timer=New-Object Windows.Forms.Timer
$timer.Interval=700
$timer.Add_Tick({
    if ($script:job) {
        if (Test-Path -LiteralPath $log) {
            $output.Text=(Get-Content -LiteralPath $log -Encoding UTF8 -Tail 100) -join "`r`n"
            $output.SelectionStart=$output.Text.Length;$output.ScrollToCaret()
        }
        if ($script:job.State -in @('Completed','Failed','Stopped')) {
            $result=Receive-Job $script:job -ErrorAction SilentlyContinue
            $success=$result -contains 'SUCCESS'
            $status.Text=if ($success) {'Pronto. Usa il collegamento MetinHub sul Desktop.'} else {'Installazione incompleta: vedi installazione_log.txt.'}
            Remove-Job $script:job -Force;$script:job=$null;$button.Enabled=$true
            $button.Text='Verifica di nuovo'
        }
    }
})
$form.Add_FormClosing({ if ($script:job -and $script:job.State -eq 'Running') { $_.Cancel=$true;$status.Text='Attendi il completamento dell operazione in corso.' } })
$timer.Start()
[void]$form.ShowDialog()
$timer.Stop();$timer.Dispose();$form.Dispose()
