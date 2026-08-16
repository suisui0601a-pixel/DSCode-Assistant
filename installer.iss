#ifndef AppVersion
  #define AppVersion "0.6.0"
#endif

#ifndef BuildSource
  #define BuildSource "release\v0.6.0\portable"
#endif

#ifndef AppIdValue
  #define AppIdValue "{{A0C1C76D-C1A1-40BE-BE30-315E26D7AE8D}"
#endif

#ifndef AppName
  #define AppName "DSCode Assistant"
#endif

#ifndef OutputDirectory
  #define OutputDirectory "release"
#endif

#ifndef OutputFilename
  #define OutputFilename "DSCode Assistant Setup v" + AppVersion
#endif

#define AppPublisher "DSCode Assistant Contributors"
#define AppExeName "DSCode Assistant.exe"

[Setup]
AppId={#AppIdValue}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL=https://github.com/suisui0601a-pixel/DSCode-Assistant
AppSupportURL=https://github.com/suisui0601a-pixel/DSCode-Assistant/issues
AppUpdatesURL=https://github.com/suisui0601a-pixel/DSCode-Assistant/releases
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
OutputDir={#OutputDirectory}
OutputBaseFilename={#OutputFilename}
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no
LicenseFile=LICENSE
VersionInfoVersion={#AppVersion}.0
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName} Windows Installer
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "{#BuildSource}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
