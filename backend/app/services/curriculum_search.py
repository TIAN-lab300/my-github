"""Search course/skill/link metadata, never present it as imported lesson evidence."""
import hashlib,re,unicodedata
from app.core.db import rows,one,run,insert
from app.services.course_links import course_links

def normalize(text):
    return re.sub(r'\s+','',unicodedata.normalize('NFKC',text)).casefold()

def rebuild(db):
    for cid,links in course_links().items():
        if not one(db,'SELECT id FROM curriculum_catalog_courses WHERE id=:c',c=cid):continue
        for link in links:
            if one(db,'SELECT id FROM curriculum_course_links WHERE course_id=:c AND url=:u',c=cid,u=link['url']):continue
            insert(db,'curriculum_course_links',id='mooc-'+hashlib.sha256((cid+link['url']).encode()).hexdigest()[:24],**link)
    run(db,'DELETE FROM curriculum_search_index')
    for c in rows(db,'SELECT id,name FROM curriculum_catalog_courses ORDER BY id'):
        skills=rows(db,'SELECT name FROM curriculum_catalog_skills WHERE course_id=:c',c=c['id'])
        chapters=rows(db,'SELECT title FROM learning_chapters WHERE course_id=:c',c=c['id'])
        links=rows(db,'SELECT title,school,note FROM curriculum_course_links WHERE course_id=:c',c=c['id'])
        text=' '.join([c['name'],*(s['name'] for s in skills),*(ch['title'] for ch in chapters),*(l['title']+' '+l['school']+' '+l['note'] for l in links)])
        text=normalize(text)
        text=re.sub(r'([\u4e00-\u9fff])',r' \1 ',text)
        run(db,'INSERT INTO curriculum_search_index(course_id,body) VALUES(:c,:b)',c=c['id'],b=text)
    return {'courses':one(db,'SELECT COUNT(*) n FROM curriculum_search_index')['n'],
        'course_links':one(db,'SELECT COUNT(*) n FROM curriculum_course_links')['n']}

def search_courses(db,query):
    needle=normalize(query)
    tokens=re.findall(r'[a-z0-9_]+|[\u4e00-\u9fff]',needle)
    if not tokens:return []
    expression=' AND '.join('"'+t+'"' for t in tokens)
    found=rows(db,'''SELECT c.*,bm25(curriculum_search_index) AS rank FROM curriculum_search_index
        JOIN curriculum_catalog_courses c ON c.id=curriculum_search_index.course_id
        WHERE curriculum_search_index MATCH :q ORDER BY rank,c.id LIMIT 36''',q=expression)
    found.sort(key=lambda c:(needle not in normalize(c['name']),c['rank'],c['id']))
    result=[]
    for c in found[:20]:
        skills=rows(db,'SELECT id,name FROM curriculum_catalog_skills WHERE course_id=:c ORDER BY id',c=c['id'])
        matched=[s for s in skills if needle in normalize(s['name'])]
        result.append({'course_id':c['id'],'name':c['name'],'year':c['year'],
            'matched_skills':matched[:8],'skill_count':len(skills),'kind':'course_metadata','usable_as_body_evidence':False,
            'links':rows(db,'SELECT title,school,url,platform,note FROM curriculum_course_links WHERE course_id=:c ORDER BY title,id',c=c['id']),
            'sources':rows(db,'''SELECT r.title,s.url FROM curriculum_catalog_sources m JOIN public_source_catalog s ON s.id=m.source_id
                JOIN resources r ON r.id=s.resource_id WHERE m.course_id=:c AND r.status='published' AND r.scope='school' ORDER BY s.id''',c=c['id'])})
    return result
