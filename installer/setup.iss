; Inno Setup script for S2T
; Requires Inno Setup 6+ — https://jrsoftware.org/isinfo.php
; Run after PyInstaller: the dist\S2T\ folder must exist.

#define AppName      "S2T"
#define AppVersion   "0.1.0"
#define AppPublisher "Jjat00"
#define AppExeName   "S2T.exe"
#define AppURL       "https://github.com/Jjat00/s2t-windows"

[Setup]
AppId={{6F3A2B1C-4D8E-4F0A-9B2C-3E5D6F7A8B9C}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
; Output installer file
OutputDir=..\dist\installer
OutputBaseFilename=S2T-Setup-{#AppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
; Require Windows 10+
MinVersion=10.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Don't need admin rights — installs per-user by default
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon";  Description: "Crear acceso directo en el escritorio"; \
      GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupicon";  Description: "Iniciar S2T con Windows"; \
      GroupDescription: "Inicio automático:"; Flags: unchecked

[Files]
; Main app files from PyInstaller output
Source: "..\dist\S2T\*"; DestDir: "{app}"; \
        Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}";               Filename: "{app}\{#AppExeName}"
Name: "{group}\Desinstalar {#AppName}";   Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}";         Filename: "{app}\{#AppExeName}"; \
      Tasks: desktopicon

[Registry]
; Optional: start with Windows
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
     ValueType: string; ValueName: "{#AppName}"; \
     ValueData: """{app}\{#AppExeName}"""; \
     Flags: uninsdeletevalue; Tasks: startupicon

[Run]
Filename: "{app}\{#AppExeName}"; \
          Description: "Iniciar {#AppName} ahora"; \
          Flags: nowait postinstall skipifsilent

[UninstallRun]
; Make sure the app isn't running when uninstalling
Filename: "taskkill"; Parameters: "/F /IM {#AppExeName}"; \
          Flags: runhidden skipifdoesntexist

[Code]
// Close running instance before install/uninstall
procedure CloseRunningInstance();
begin
  Exec('taskkill', '/F /IM {#AppExeName}', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
    CloseRunningInstance();
end;
