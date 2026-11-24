"""Public map links for identifiable OpenStreetMap objects."""
import re


def osm_place_url(source_id):
    if not isinstance(source_id, str) or not re.fullmatch(r'(?:node|way|relation)/[1-9][0-9]*', source_id):
        return None
    return 'https://www.openstreetmap.org/' + source_id
