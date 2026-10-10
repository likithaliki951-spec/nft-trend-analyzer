---
name: Replit preview routing
description: The project uses artifact path routing for browser previews.
---

Register browser-facing services in an artifact manifest with an explicit service path. A generic workflow listening on a port, and a `.replit` port mapping by itself, do not guarantee a previewable root route in this path-routed workspace. For Streamlit, explicitly route `/_stcore/stream` as well so the browser WebSocket is proxied.

**Why:** Replit's preview router reported “no previewable artifacts” until the Streamlit service was registered at the root preview path; the page then stayed blank until the Streamlit WebSocket path was included.

**How to apply:** For new web apps here, use a root artifact route that forwards to the actual service port, preserve existing API paths, and verify with a browser preview rather than relying only on an open port.
