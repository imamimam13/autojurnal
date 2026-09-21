Set WshShell = CreateObject("WScript.Shell")
Dim fso, scriptDir
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

' Jalankan run.bat tanpa memunculkan jendela hitam CMD (0 = invisible)
WshShell.CurrentDirectory = scriptDir
WshShell.Run """" & scriptDir & "\run.bat""", 0, False
