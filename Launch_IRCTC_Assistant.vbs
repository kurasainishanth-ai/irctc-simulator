Set WshShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")
Set objWMIService = GetObject("winmgmts:\\.\root\cimv2")

currentDir = objFSO.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = currentDir

' 1. Start the Flask server hidden if not already running
serverRunning = False
Set colProcesses = objWMIService.ExecQuery("Select * from Win32_Process Where Name = 'pythonw.exe' Or Name = 'python.exe'")
For Each objProcess in colProcesses
    If Not IsNull(objProcess.CommandLine) Then
        If InStr(objProcess.CommandLine, "assistant_server.py") > 0 Then
            serverRunning = True
        End If
    End If
Next

If Not serverRunning Then
    WshShell.Run "pythonw assistant_server.py", 0, False
End If

' 2. Start Chrome with CDP if not already running
chromeProfile = currentDir & "\chrome_profile"

chromeRunning = False
Set colChrome = objWMIService.ExecQuery("Select * from Win32_Process Where Name = 'chrome.exe'")
For Each objChrome In colChrome
    If Not IsNull(objChrome.CommandLine) Then
        If InStr(objChrome.CommandLine, "--remote-debugging-port=9222") > 0 Then
            chromeRunning = True
        End If
    End If
Next

If Not chromeRunning Then
    chromeCmd = "chrome.exe --remote-debugging-port=9222 --user-data-dir=""" & chromeProfile & """ --no-first-run --no-default-browser-check"
    WshShell.Run chromeCmd, 1, False
End If

' 3. Wait until CDP is responsive
cdpReady = False
For i = 1 To 20
    Set xmlHttp = CreateObject("MSXML2.ServerXMLHTTP.6.0")
    On Error Resume Next
    xmlHttp.open "GET", "http://127.0.0.1:9222/json/version", False
    xmlHttp.send
    If Err.Number = 0 Then
        If xmlHttp.Status = 200 Then
            cdpReady = True
            Exit For
        End If
    End If
    On Error GoTo 0
    WScript.Sleep 500
Next

If Not cdpReady Then
    MsgBox "Failed to start Chrome CDP on port 9222. Please ensure no other Chrome instance is blocking the port.", vbCritical, "Startup Error"
    WScript.Quit
End If

' 4. Wait until Backend is responsive
backendReady = False
For i = 1 To 20
    Set xmlHttp = CreateObject("MSXML2.ServerXMLHTTP.6.0")
    On Error Resume Next
    xmlHttp.open "GET", "http://127.0.0.1:5005/api/status", False
    xmlHttp.send
    If Err.Number = 0 Then
        If xmlHttp.Status = 200 Then
            backendReady = True
            Exit For
        End If
    End If
    On Error GoTo 0
    WScript.Sleep 500
Next

If Not backendReady Then
    MsgBox "Failed to start the local backend server on port 5005.", vbCritical, "Startup Error"
    WScript.Quit
End If

' 5. Query existing tabs to avoid opening duplicates
Set xmlHttp = CreateObject("MSXML2.ServerXMLHTTP.6.0")
On Error Resume Next
xmlHttp.open "GET", "http://127.0.0.1:9222/json", False
xmlHttp.send
jsonTabs = xmlHttp.responseText
On Error GoTo 0

hasIrctc = False
hasAssistant = False

If InStr(jsonTabs, "irctc.co.in") > 0 Then
    hasIrctc = True
End If
If InStr(jsonTabs, "127.0.0.1:5005") > 0 Or InStr(jsonTabs, "localhost:5005") > 0 Then
    hasAssistant = True
End If

urlsToOpen = ""
If Not hasIrctc Then
    urlsToOpen = urlsToOpen & " https://www.irctc.co.in/nget/"
End If
urlsToOpen = urlsToOpen & " http://127.0.0.1:5005"

chromeOpenTabsCmd = "chrome.exe --user-data-dir=""" & chromeProfile & """" & urlsToOpen
WshShell.Run chromeOpenTabsCmd, 1, False
