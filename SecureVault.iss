[Setup]
AppName=SecureVault
AppVersion=1.1
DefaultDirName={pf}\SecureVault
DefaultGroupName=SecureVault
OutputDir=.
OutputBaseFilename=SecureVault_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Files]
Source: "dist\SecureVault.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\encryptor.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\SecureVault"; Filename: "{app}\SecureVault.exe"
Name: "{commondesktop}\SecureVault"; Filename: "{app}\SecureVault.exe"

[Run]
Filename: "{app}\SecureVault.exe"; Description: "Launch SecureVault"; Flags: nowait postinstall skipifsilent