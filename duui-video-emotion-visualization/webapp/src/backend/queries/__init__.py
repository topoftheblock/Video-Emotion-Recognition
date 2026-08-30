"""Every SQL statement the webapp runs, grouped by what it reads.

Kept apart from `backend.routes` so the queries can be exercised
without going through HTTP, and so a route body stays readable as
"fetch this, shape it, return it". Nothing here knows about FastAPI,
request objects or status codes: a missing row is reported as None or
an empty list, and turning that into a 404 is the route's job.
"""
