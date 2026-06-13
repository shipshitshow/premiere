# Legacy ExtendScript (quarantined)

These `.jsx` files are **legacy ExtendScript** from an earlier workflow. They are
**not** part of the active Adobe MCP editing path and are **not invoked by any
code** in this repo. They are kept only for reference / manual recovery.

The active workflow drives Premiere through the MCP server and UXP plugin under
`apps/premiere/adobe-mcp`. ExtendScript (`.jsx`) is a separate, older Premiere
automation surface that the UXP plugin replaces.

| File | Old purpose |
| --- | --- |
| `import-media.jsx` | Import media files into a project. |
| `create-sequence.jsx` | Create a sequence from imported media. |
| `add-markers.jsx` | Add timeline markers. |
| `export-sequence.jsx` | Export a sequence via the render queue. |

To do any of these through the supported path, use the MCP tools instead
(e.g. `premiere_create_sequence`, `premiere_export_sequence`,
`premiere_insert_mogrt`, transcript import/export tools). Do not wire these
`.jsx` files back into the live workflow without an explicit decision to revive
the ExtendScript path.
