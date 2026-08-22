"""Reading a CAS: view selection, typesystem loading, and person resolution.

Every parser step depends on this package and on nothing else structural in the
importer. Kept together because that is what makes the boundary real: the
modules here understand UIMA, and nothing outside `parsers/` needs to.
"""
