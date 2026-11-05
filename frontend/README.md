# Lumen interface

React + TypeScript frontend for the real local Python service. Includes Capture,
Transfers, editable Preview, Library and Settings. Run `npm ci` and `npm run build`
in this folder, then start `tools/open_interface.py` from the project root with
your configured Python environment. See the root README for destinations and setup.

`src/service.ts` defines the typed transport. `/api` is served on the same loopback
origin as the compiled interface. Credentials and local state are never bundled.
The GitHub Pages website is a showcase, not a remotely connected transfer client.
