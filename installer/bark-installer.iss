; Bark - Inno Setup installer script (PyInstaller bundle)
; Build: Run build-release.bat (or manually: pyinstaller bark.spec --clean, then ISCC this file)
; Output: build\Bark-{version}-Setup.exe

#define AppVersion "1.3.1"

[Setup]
AppName=Bark
AppVersion={#AppVersion}
AppPublisher=LAB37
AppPublisherURL=https://lab37.io
DefaultDirName={localappdata}\Bark
DefaultGroupName=Bark
DisableProgramGroupPage=yes
OutputDir=build
OutputBaseFilename=Bark-{#AppVersion}-Setup
SetupIconFile=..\icon.ico
UninstallDisplayIcon={app}\Bark.exe
PrivilegesRequired=lowest
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
MinVersion=10.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
; PyInstaller onedir output -- everything under dist\Bark\
Source: "..\dist\Bark\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Bark"; Filename: "{app}\Bark.exe"; IconFilename: "{app}\Bark.exe"; WorkingDir: "{app}"; AppUserModelID: "lab37.bark"
Name: "{autodesktop}\Bark"; Filename: "{app}\Bark.exe"; IconFilename: "{app}\Bark.exe"; WorkingDir: "{app}"; Tasks: desktopicon; AppUserModelID: "lab37.bark"

[UninstallDelete]
Type: files; Name: "{app}\dictation.log"
Type: files; Name: "{app}\bark_config.json"
Type: files; Name: "{app}\bark_history.txt"
Type: files; Name: "{app}\bark_history.old.txt"
Type: files; Name: "{app}\.bark.lock"
Type: filesandordirs; Name: "{app}\_internal"
