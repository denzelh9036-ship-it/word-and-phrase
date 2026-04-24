# -*- mode: python ; coding: utf-8 -*-

block_cipher = None


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[('static', 'static')],
    hiddenimports=[
        'tk_views',
        'tk_views.auth_view',
        'tk_views.book_view',
        'tk_views.images',
        'tk_views.main_view',
        'tk_views.search_view',
        'tk_views.study_view',
        'tk_views.theme',
        'tk_views.widgets',
        'tk_client',
        'auth',
        'db',
        'dictionary',
        'srs',
        'main',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='WordAndPhrase',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='WordAndPhrase',
)

app = BUNDLE(
    coll,
    name='Word & Phrase.app',
    icon=None,
    bundle_identifier='com.wordandphrase.app',
    info_plist={
        'CFBundleName': 'Word & Phrase',
        'CFBundleDisplayName': 'Word & Phrase',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '11.0',
    },
)
