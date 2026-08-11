# Interfaces

- **fnpqnn-gateway CLI:** use only through the documented repository route.
- **MCP server:** use only through the documented repository route.
- **Typed adapter boundary:** use only through the documented repository route.
- **Suite auth audit:** validates the twelve repository adapter templates and fails closed on missing policy or forbidden secret material.
- **Fingerprint acceptance:** records a bounded, non-secret approval reference after provider-native authentication.
- **Application boundary:** every product owns its actual login UI, callback, account binding, session lifecycle, logout, and recovery.

## Interface contract

Inputs must be explicit, outputs must be inspectable, errors must be returned as errors, and consequential external actions require human approval.

## Compatibility

Treat undocumented endpoints, commands, and browser controls as unsupported. Confirm the current repository version before integrating another system.
