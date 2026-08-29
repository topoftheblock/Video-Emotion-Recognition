"""Reading a CAS: view selection, typesystem loading, person resolution.

Every parser step depends on this package and on nothing else
structural in the importer. Keeping these modules together is what
makes the boundary real: the code here understands UIMA, and nothing
outside `parsers/` needs to.
"""
