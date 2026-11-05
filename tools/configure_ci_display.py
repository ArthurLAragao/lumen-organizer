"""Give Windows-hosted Tk geometry tests a full-size display, only in GitHub Actions."""
import ctypes
import os
import struct
import sys

if os.environ.get('GITHUB_ACTIONS') != 'true' or sys.platform != 'win32':
    raise SystemExit('This display helper is restricted to Windows GitHub Actions runners.')

user = ctypes.windll.user32
mode = ctypes.create_string_buffer(220)
struct.pack_into('<H', mode, 68, 220)
if not user.EnumDisplaySettingsW(None, -1, ctypes.byref(mode)):
    raise SystemExit('Unable to inspect the CI display.')
print('Initial display:', struct.unpack_from('<II', mode, 172))
struct.pack_into('<II', mode, 172, 2560, 1440)
fields = struct.unpack_from('<I', mode, 72)[0]
struct.pack_into('<I', mode, 72, fields | 0x80000 | 0x100000)
result = user.ChangeDisplaySettingsW(ctypes.byref(mode), 0)
if result != 0:
    raise SystemExit(f'Unable to configure the required CI display (code {result}).')
print('Tk test display: 2560 x 1440')
