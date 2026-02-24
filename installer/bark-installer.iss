; Bark - Inno Setup installer script
; Build: Install Inno Setup 6, then run build-win-installer.bat
; Output: build\Bark-Setup.exe

[Setup]
AppName=Bark
AppVersion=1.2.1
AppPublisher=LAB37
AppPublisherURL=https://lab37.se
DefaultDirName={localappdata}\Bark
DefaultGroupName=Bark
DisableProgramGroupPage=yes
OutputDir=build
OutputBaseFilename=Bark-Setup
SetupIconFile=..\icon.ico
UninstallDisplayIcon={app}\icon.ico
PrivilegesRequired=lowest
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
MinVersion=10.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
; Python source
Source: "..\dictation.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\audio.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\transcriber.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\keyboard_hook.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\overlay.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\feedback.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\config.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\tray.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\history.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\version_check.py"; DestDir: "{app}"; Flags: ignoreversion
; Support files
Source: "..\icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\VERSION"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\requirements.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\start.bat"; DestDir: "{app}"; Flags: ignoreversion
; Setup script
Source: "setup-win.bat"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Bark"; Filename: "{app}\start.bat"; IconFilename: "{app}\icon.ico"; WorkingDir: "{app}"; AppUserModelID: "lab37.bark"
Name: "{autodesktop}\Bark"; Filename: "{app}\start.bat"; IconFilename: "{app}\icon.ico"; WorkingDir: "{app}"; Tasks: desktopicon; AppUserModelID: "lab37.bark"

[Run]
Filename: "cmd.exe"; Parameters: "/c ""{app}\setup-win.bat"""; WorkingDir: "{app}"; Description: "Set up Python environment (required)"; Flags: postinstall nowait

[UninstallDelete]
Type: filesandordirs; Name: "{app}\.venv"
Type: filesandordirs; Name: "{app}\__pycache__"
Type: files; Name: "{app}\dictation.log"
