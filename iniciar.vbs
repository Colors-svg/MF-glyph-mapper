' MF Glyph Mapper — lanzador sin consola (app de escritorio).
' Uso: doble clic. Arranca el servidor oculto y abre la ventana de la app.
Option Explicit
Dim sh, fso, root, port, url, chrome, edge, wmi, procs, p
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)
port = "8765"
url = "http://127.0.0.1:" & port & "/"
' Detener servidor anterior de este proyecto (si lo hay)
On Error Resume Next
Set wmi = GetObject("winmgmts:\\.\root\cimv2")
Set procs = wmi.ExecQuery("SELECT * FROM Win32_Process WHERE Name='python.exe' OR Name='pythonw.exe'")
For Each p In procs
  If InStr(p.CommandLine, "mf-glyph-mapper") > 0 And InStr(p.CommandLine, "server.py") > 0 Then p.Terminate()
Next
On Error GoTo 0
' Servidor oculto (pythonw = sin consola)
sh.Run "pythonw -u web\server.py --port " & port, 0, False
' Esperar hasta 60 s a que responda (carpeta del script como cwd)
sh.CurrentDirectory = root
Dim ok, i
ok = False
For i = 1 To 30
  WScript.Sleep 2000
  Dim http
  Set http = CreateObject("MSXML2.XMLHTTP")
  On Error Resume Next
  http.open "GET", url, False
  http.send
  If Err.Number = 0 And http.status = 200 Then ok = True
  On Error GoTo 0
  If ok Then Exit For
Next
If Not ok Then
  MsgBox "El servidor no respondió en " & url & ". Revisa tu instalación de Python/Manim.", 16, "MF Glyph Mapper"
  WScript.Quit 1
End If
' Ventana de app (Chrome --app, Edge --app, o navegador por defecto)
chrome = sh.ExpandEnvironmentStrings("%ProgramFiles%") & "\Google\Chrome\Application\chrome.exe"
edge = sh.ExpandEnvironmentStrings("%ProgramW6432%") & "\Microsoft\Edge\Application\msedge.exe"
If fso.FileExists(chrome) Then
  sh.Run """" & chrome & """ --app=" & url & " --user-data-dir=""" & sh.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\MF-Glyph-Mapper-App""", 1, False
ElseIf fso.FileExists(edge) Then
  sh.Run """" & edge & """ --app=" & url, 1, False
Else
  sh.Run url, 1, False
End If
