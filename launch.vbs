' Bark - Silent launcher for Windows
' Runs Bark without showing a console window.
' Falls back to setup-win.bat if the virtual environment is missing or outdated.

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

' Get directory where this script lives
dir = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = dir

pythonw = dir & "\.venv\Scripts\pythonw.exe"
needSetup = False

' Check 1: venv exists?
If Not fso.FileExists(pythonw) Then
    needSetup = True
End If

' Check 2: version mismatch? (setup ran for older version)
If Not needSetup Then
    setupVer = ""
    appVer = ""
    On Error Resume Next
    If fso.FileExists(dir & "\.setup-version") Then
        Set f = fso.OpenTextFile(dir & "\.setup-version", 1)
        setupVer = Trim(f.ReadLine())
        f.Close
    End If
    If fso.FileExists(dir & "\VERSION") Then
        Set f = fso.OpenTextFile(dir & "\VERSION", 1)
        appVer = Trim(f.ReadLine())
        f.Close
    End If
    On Error GoTo 0
    If setupVer <> appVer Then needSetup = True
End If

' Run setup if needed (visible cmd window, wait for completion)
If needSetup Then
    setupBat = ""
    If fso.FileExists(dir & "\setup-win.bat") Then
        setupBat = dir & "\setup-win.bat"
    ElseIf fso.FileExists(dir & "\installer\setup-win.bat") Then
        setupBat = dir & "\installer\setup-win.bat"
    End If

    If setupBat <> "" Then
        shell.Run """" & setupBat & """", 1, True
    Else
        MsgBox "setup-win.bat not found." & vbCrLf & vbCrLf & "Re-download Bark from https://github.com/delarc0/bark", vbCritical, "Bark"
        WScript.Quit 1
    End If

    ' Verify setup succeeded
    If Not fso.FileExists(pythonw) Then
        MsgBox "Setup failed. Check the setup window for errors.", vbCritical, "Bark"
        WScript.Quit 1
    End If
End If

' Launch Bark silently (window style 0 = hidden)
shell.Run """" & pythonw & """ """ & dir & "\dictation.py""", 0, False
