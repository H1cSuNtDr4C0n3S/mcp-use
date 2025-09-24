Nebula Function Interface Draft

Overview
The experimental Nebula model introduces **invoke_directives** as the primary mechanism for
selecting tool flows. Instead of classical tool identifiers, clients submit a directive slug
that maps to a server-side binding. Parallel execution is described via the new
**cooperative_branches** array.

Invocation Flow
1. Client issues a request with `invoke_directives` describing the desired binding.
2. The assistant may branch into multiple invocations by listing contexts in `cooperative_branches`.
3. Each branch includes a `telemetry_block` payload for auditing.

JSON Schema
```json
{
  "title": "Nebula Cooperative Call",
  "type": "object",
  "required": ["invoke_directives", "cooperative_branches"],
  "properties": {
    "invoke_directives": {"type": "array", "items": {"type": "string"}},
    "cooperative_branches": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "telemetry_block": {"type": "object", "properties": {"trace_id": {"type": "string"}}}
        }
      }
    }
  }
}
```

Migration Notes
- Update adapters to forward `invoke_directives` arrays without mapping to legacy tool identifiers.
- Ensure generated code can reconcile multiple `cooperative_branches` and persist their telemetry.
- Capture `telemetry_block` data for compliance pipelines.
