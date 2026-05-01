Set oShell = CreateObject("WScript.Shell")
oShell.Run """" & Replace(WScript.ScriptFullName, WScript.ScriptName, "") & "iniciar_automatic.bat""", 0, False