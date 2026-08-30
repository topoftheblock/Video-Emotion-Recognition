"""The HTTP surface, one module per group of endpoints.

Each module exposes a `router` that `backend.app` wires up. Route
bodies stay thin on purpose: they validate the request, call into
`backend.queries`, and turn "nothing found" into a 404. The SQL itself
lives next door.
"""
