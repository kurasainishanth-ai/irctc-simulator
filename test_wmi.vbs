Set objWMIService = GetObject("winmgmts:\\.\root\cimv2")
Set colProcesses = objWMIService.ExecQuery("Select * from Win32_Process Where Name = 'pythonw.exe' Or Name = 'python.exe'")
For Each objProcess in colProcesses
    If Not IsNull(objProcess.CommandLine) Then
        WScript.Echo objProcess.CommandLine
    End If
Next
