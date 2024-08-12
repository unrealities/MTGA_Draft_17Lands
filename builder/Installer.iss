; -- MtgaDraft.iss --
[Setup]
AppName=MTGA Draft Tool
AppVersion=3.27
WizardStyle=modern
DefaultDirName={sd}\MtgaDraftTool
DefaultGroupName=MtgaDraftTool
LicenseFile=..\LICENSE
UninstallDisplayIcon={app}\MtgaDraftTool.exe
Compression=lzma2
UsePreviousAppDir=yes
SolidCompression=yes
OutputDir={app}
OutputBaseFilename=MTGA_Draft_Tool_V0327
InfoAfterFile=..\release_notes.txt
[Files]
Source: "..\dist\MTGA_Draft_Tool.exe"; DestDir: "{app}"
Source: "..\README.md"; DestDir: "{app}"
Source: "..\release_notes.txt"; DestDir: "{app}"
Source: "..\dark_mode.tcl"; DestDir: "{app}"
Source: "..\Tools\TierScraper17Lands\src\17LandsTier.css"; DestDir: "{app}\Tools\TierScraper17Lands"
Source: "..\Tools\TierScraper17Lands\src\17LandsTier.js"; DestDir: "{app}\Tools\TierScraper17Lands"
Source: "..\Tools\TierScraper17Lands\src\manifest.json"; DestDir: "{app}\Tools\TierScraper17Lands"
Source: "..\Tools\TierScraper17Lands\README.md"; DestDir: "{app}\Tools\TierScraper17Lands"
[Icons]
Name: "{group}\MtgaDraftTool"; Filename: "{app}\MTGA_Draft_Tool.exe"

[Dirs]
Name: {app}\Tools\TierScraper17Lands
