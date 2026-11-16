"""Curated original-site learning entries; not local playable or indexed media."""
import json
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

@lru_cache(maxsize=1)
def course_links():
    path=Path(__file__).resolve().parents[3]/'docs/curriculum/mooc-course-links.json'
    payload=json.loads(path.read_text(encoding='utf-8'));grouped={};seen=set()
    for item in payload['courses']:
        url=urlsplit(item['url'])
        if url.scheme!='https' or url.netloc!='www.icourse163.org' or not url.path.startswith('/course/'):
            raise ValueError('Course entries must point to the reviewed MOOC course site')
        key=(item['course_id'],item['url'])
        if key in seen:raise ValueError('Duplicate course entry')
        seen.add(key)
        grouped.setdefault(item['course_id'],[]).append({**item,'platform':'中国大学MOOC',
            'checked_at':payload['checked_at'],'verification':payload['verification']})
    return grouped
