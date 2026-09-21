using System;
using System.IO;
using System.Diagnostics;
using System.Threading;
using System.Windows.Forms;
using System.Runtime.InteropServices;
using System.Reflection;
[assembly: AssemblyTitle("MetinHub")]
[assembly: AssemblyDescription("Avviatore MetinHub")]
[assembly: AssemblyVersion("0.1.0.0")]
class Launcher {
    [DllImport("shell32.dll", CharSet=CharSet.Unicode)]
    static extern int SetCurrentProcessExplicitAppUserModelID(string id);
    static void RegistraErrore(string text) {
        try {
            string path=Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"metinhub_log.txt");
            if (File.Exists(path) && new FileInfo(path).Length>1000000) {
                string backup=path+".1";
                if (File.Exists(backup)) File.Delete(backup);
                File.Move(path,backup);
            }
            File.AppendAllText(path,DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss")+" | ERROR | Avviatore: "+text+Environment.NewLine);
        } catch { /* Il messaggio a schermo rimane disponibile se il disco non e scrivibile. */ }
    }
    [STAThread] static void Main() {
        bool first;
        using (Mutex mutex = new Mutex(true,"Local\\MetinHub.Desktop.Launcher",out first)) {
            if (!first) { MessageBox.Show("MetinHub risulta gia aperto.","MetinHub"); return; }
            try {
                SetCurrentProcessExplicitAppUserModelID("MetinHub.Desktop");
                string folder=AppDomain.CurrentDomain.BaseDirectory;
                string python=Path.Combine(folder,@".venv\Scripts\pythonw.exe");
                string script=Path.Combine(folder,"osserva_metin.py");
                if (!File.Exists(python) || !File.Exists(script)) {
                    MessageBox.Show("Componenti mancanti. Apri Installa_MetinHub.bat nella cartella del programma.","MetinHub"); return;
                }
                ProcessStartInfo check=new ProcessStartInfo(Path.Combine(folder,@".venv\Scripts\python.exe"),"\""+Path.Combine(folder,"setup_check.py")+"\" bootstrap");
                check.WorkingDirectory=folder; check.UseShellExecute=false; check.CreateNoWindow=true;
                using (Process test=Process.Start(check)) {
                    if (!test.WaitForExit(30000)) { test.Kill(); MessageBox.Show("Verifica di avvio scaduta. Esegui Installa_MetinHub.bat.","MetinHub"); return; }
                    if (test.ExitCode!=0) {
                        if (MessageBox.Show("Mancano componenti per aprire l'app. Aprire l'installazione?","MetinHub",MessageBoxButtons.YesNo)==DialogResult.Yes) {
                            Process.Start(new ProcessStartInfo(Path.Combine(folder,"Installa_MetinHub.bat")) { UseShellExecute=true, WorkingDirectory=folder });
                        }
                        return;
                    }
                }
                ProcessStartInfo start=new ProcessStartInfo(python,"\""+script+"\"");
                start.WorkingDirectory=folder;
                start.UseShellExecute=false;
                using (Process p=Process.Start(start)) {
                    p.WaitForExit();
                    if (p.ExitCode!=0) { RegistraErrore("Processo terminato con codice "+p.ExitCode); MessageBox.Show("Avvio interrotto. Controlla metinhub_log.txt oppure esegui Installa_MetinHub.bat per verificare i componenti.","MetinHub"); }
                }
            } catch(Exception ex) { RegistraErrore(ex.ToString()); MessageBox.Show(ex.Message,"MetinHub - avvio non riuscito"); }
        }
    }
}
