; Installer script for Universal Media Downloader. Build with:
;   ISCC.exe /DAppVersion=1.1.0 installer.iss
; Expects a finished PyInstaller build in dist\UniversalMediaDownloader\.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

#define AppName "Universal Media Downloader"
#define AppShortName "UniversalMediaDownloader"
#define AppPublisher "Magerko"
#define AppURL "https://github.com/Magerko/universal-media-downloader"
#define AppExeName "UniversalMediaDownloader.exe"

[Setup]
; Keep this GUID stable forever - it is how Windows recognises an upgrade of an
; existing install rather than a second copy.
AppId={{4CEAAEA2-B4C9-4C47-9F31-898CB40CAFCA}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
AppUpdatesURL={#AppURL}/releases
VersionInfoVersion={#AppVersion}

; Install into the user profile so no admin rights and no UAC prompt are needed.
; An unsigned installer that also demands elevation is what actually scares
; people off; without it Windows shows a far milder warning.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DefaultDirName={autopf}\{#AppShortName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes

ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

OutputDir=installer_output
OutputBaseFilename={#AppShortName}-{#AppVersion}-setup
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\{#AppExeName}
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
LicenseFile=LICENSE

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "ukrainian"; MessagesFile: "compiler:Languages\Ukrainian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\UniversalMediaDownloader\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\UniversalMediaDownloader\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion
Source: "vendor\FFMPEG-LICENSE.txt"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
