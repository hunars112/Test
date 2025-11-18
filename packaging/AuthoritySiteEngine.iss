; Inno Setup script template for Authority Site Engine
#define MyAppName "Authority Site Engine"
#define MyAppVersion "{{VERSION}}"
#define MyAppPublisher "Authority Site Engine"
#define MyAppExeName "AuthoritySiteEngine.exe"
#define MyAppDist "{{DIST_DIR}}"

[Setup]
AppId={{5E2C8E7F-6A62-4F74-AD49-4DBB2B6C78C1}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={pf}\Authority Site Engine
DefaultGroupName=Authority Site Engine
DisableProgramGroupPage=yes
OutputBaseFilename=AuthoritySiteEngineSetup
OutputDir=installer
Compression=lzma
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "{#MyAppDist}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Authority Site Engine"; Filename: "{app}\{#MyAppExeName}"
Name: "{commondesktop}\Authority Site Engine"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Authority Site Engine"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{userappdata}\AuthoritySiteEngine"
