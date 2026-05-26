# PyInstaller version-info file for YancoHub.exe.
# Embeds proper Windows file/product metadata so File Properties → Details
# shows real values and SmartScreen heuristics treat the binary as a real app.
# Keep VERSION in sync with constants.py (build.py patches the numeric tuple
# at build time).

VSVersionInfo(
    ffi=FixedFileInfo(
        # filevers / prodvers — 4-tuple of ints; build.py rewrites these from constants.VERSION
        filevers=(1, 0, 0, 0),
        prodvers=(1, 0, 0, 0),
        mask=0x3F,
        flags=0x0,
        OS=0x40004,         # VOS_NT_WINDOWS32
        fileType=0x1,       # VFT_APP
        subtype=0x0,
        date=(0, 0),
    ),
    kids=[
        StringFileInfo([
            StringTable(
                '040904B0',  # English (US), Unicode codepage
                [
                    StringStruct('CompanyName',      'Yaman Addas'),
                    StringStruct('FileDescription',  'YancoHub — unified PC game launcher'),
                    StringStruct('FileVersion',      '1.0.0.0'),
                    StringStruct('InternalName',     'YancoHub'),
                    StringStruct('LegalCopyright',   '© Yaman Addas'),
                    StringStruct('OriginalFilename', 'YancoHub.exe'),
                    StringStruct('ProductName',      'YancoHub'),
                    StringStruct('ProductVersion',   '1.0.0'),
                ],
            ),
        ]),
        VarFileInfo([VarStruct('Translation', [0x0409, 1200])]),
    ],
)
