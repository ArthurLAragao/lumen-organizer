"""One-click operational workspace, independent of a development terminal."""
from open_interface import main

if __name__ == '__main__':
    import sys
    import webbrowser
    main()
    from lumen_organizer.desktop import open_app
    open_app('http://127.0.0.1:4180/')
