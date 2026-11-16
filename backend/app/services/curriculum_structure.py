"""Project curriculum structure: explicit DAGs, immutable versions, no guessed mastery."""
import hashlib,json
from pathlib import Path
from app.core.db import transaction,one,rows,run,insert,now,dump,audit
from app.core.security import fail
SOURCE=Path(__file__).resolve().parents[3]/'docs/curriculum/curriculum-relations.json'


def topological_order(nodes,edges):
    nodes=set(nodes);incoming={n:0 for n in nodes};following={n:[] for n in nodes};seen=set()
    for e in edges:
        before,after=e['before_id'],e['after_id']
        if before not in nodes or after not in nodes or before==after:raise ValueError('Invalid prerequisite endpoint')
        if (before,after) in seen:raise ValueError('Duplicate prerequisite edge')
        seen.add((before,after));incoming[after]+=1;following[before].append(after)
    ready=sorted(n for n in nodes if not incoming[n]);ordered=[]
    while ready:
        n=ready.pop(0);ordered.append(n)
        for following_node in sorted(following[n]):
            incoming[following_node]-=1
            if not incoming[following_node]:ready.append(following_node);ready.sort()
    if len(ordered)!=len(nodes):raise ValueError('Prerequisite cycle detected')
    return ordered


def validate(payload):
    courses=payload['courses'];course_ids={c['id'] for c in courses};chapters={};skills={}
    if len(course_ids)!=len(courses):raise ValueError('Duplicate courses')
    for c in courses:
        positions=set()
        for ch in c['chapters']:
            if ch['id'] in chapters or ch['position'] in positions:raise ValueError('Duplicate chapters or positions')
            chapters[ch['id']]=c['id'];positions.add(ch['position'])
            for s in ch['skill_ids']:
                if s in skills:raise ValueError('A knowledge point belongs to more than one chapter')
                skills[s]=c['id']
    for key,nodes in [('course_edges',course_ids),('skill_edges',skills),('chapter_edges',chapters)]:
        topological_order(nodes,payload[key])
        if any(e['kind'] not in ('required','recommended') or not e['reason'].strip() for e in payload[key]):raise ValueError('Missing prerequisite rationale')
        if key!='course_edges' and any(nodes[e['before_id']]!=nodes[e['after_id']] for e in payload[key]):raise ValueError('Local dependency crosses course boundary')
    if any(r['course_id'] not in course_ids for r in payload['external_requirements']):raise ValueError('Unknown external requirement course')
    return courses,skills


def import_structure(source=SOURCE):
    payload=json.loads(Path(source).read_text(encoding='utf-8'));courses,skills=validate(payload)
    digest=hashlib.sha256(dump(payload).encode()).hexdigest();version=payload['version']
    with transaction() as db:
        old=one(db,'SELECT * FROM curriculum_relation_versions WHERE id=:i',i=version)
        if old:
            if old['payload_hash']!=digest:raise ValueError('Version is immutable; register a new version')
            return {'version':version,'already_imported':True}
        admin=one(db,"SELECT id FROM users WHERE role='admin' AND status='active' ORDER BY created_at LIMIT 1")
        if not admin:raise ValueError('An existing administrator is required')
        for c in courses:
            if not one(db,'SELECT id FROM curriculum_catalog_courses WHERE id=:i',i=c['id']):raise ValueError('Missing course '+c['id'])
            actual={s['id'] for s in rows(db,'SELECT id FROM curriculum_catalog_skills WHERE course_id=:c',c=c['id'])}
            expected={s for ch in c['chapters'] for s in ch['skill_ids']}
            if actual!=expected:raise ValueError('Course knowledge scope has changed: '+c['id'])
            for ch in c['chapters']:
                oldchapter=one(db,'SELECT * FROM learning_chapters WHERE course_id=:c AND (id=:i OR position=:p)',c=c['id'],i=ch['id'],p=ch['position'])
                if oldchapter and (oldchapter['id']!=ch['id'] or oldchapter['title']!=ch['title']):raise ValueError('Preserving existing manual chapter: '+oldchapter['id'])
                if not oldchapter:insert(db,'learning_chapters',id=ch['id'],course_id=c['id'],title=ch['title'],position=ch['position'])
                for s in ch['skill_ids']:
                    oldlink=one(db,'SELECT chapter_id FROM learning_skill_chapters WHERE skill_id=:s',s=s)
                    if oldlink and oldlink['chapter_id']!=ch['id']:raise ValueError('Preserving manual knowledge assignment: '+s)
                    if not oldlink:insert(db,'learning_skill_chapters',skill_id=s,chapter_id=ch['id'],course_id=c['id'])
        insert(db,'curriculum_relation_versions',id=version,payload_hash=digest,basis=payload['basis'],created_at=now())
        for key,table in [('course_edges','curriculum_course_prerequisites'),('skill_edges','curriculum_skill_prerequisites'),('chapter_edges','curriculum_chapter_prerequisites')]:
            for e in payload[key]:insert(db,table,version_id=version,**e)
        for r in payload['external_requirements']:insert(db,'curriculum_external_requirements',version_id=version,**r)
        run(db,'UPDATE curriculum_relation_versions SET active=0 WHERE active=1')
        run(db,'UPDATE curriculum_relation_versions SET active=1 WHERE id=:i',i=version)
        from app.services.curriculum_search import rebuild
        rebuild(db)
        audit(db,admin['id'],'curriculum_structure_imported',version,dump({'courses':len(courses),'skills':len(skills)}))
    return {'version':version,'courses':len(courses),'chapters':sum(len(c['chapters']) for c in courses),'skills':len(skills),
        **{key:len(payload[key]) for key in ('course_edges','skill_edges','chapter_edges','external_requirements')}}


def structure(db,course_id):
    version=one(db,'SELECT * FROM curriculum_relation_versions WHERE active=1')
    chapters=rows(db,'SELECT * FROM learning_chapters WHERE course_id=:c ORDER BY position',c=course_id)
    for ch in chapters:ch['skills']=rows(db,'''SELECT s.id,s.name FROM learning_skill_chapters m JOIN curriculum_catalog_skills s ON s.id=m.skill_id WHERE m.chapter_id=:i ORDER BY s.id''',i=ch['id'])
    result={'version':version,'chapters':chapters,'course_prerequisites':[],'skill_prerequisites':[],'chapter_prerequisites':[],'external_requirements':[]}
    if not version:return result
    v=version['id']
    result['course_prerequisites']=rows(db,'''SELECT p.*,c.name FROM curriculum_course_prerequisites p
        JOIN curriculum_catalog_courses c ON c.id=p.before_id WHERE p.version_id=:v AND p.after_id=:c ORDER BY p.kind,p.before_id''',v=v,c=course_id)
    result['skill_prerequisites']=rows(db,'''SELECT p.*,s.name AS before_name,t.name AS after_name FROM curriculum_skill_prerequisites p
        JOIN curriculum_catalog_skills s ON s.id=p.before_id JOIN curriculum_catalog_skills t ON t.id=p.after_id
        WHERE p.version_id=:v AND t.course_id=:c ORDER BY p.after_id,p.before_id''',v=v,c=course_id)
    result['chapter_prerequisites']=rows(db,'''SELECT p.*,b.title AS before_name,a.title AS after_name FROM curriculum_chapter_prerequisites p
        JOIN learning_chapters b ON b.id=p.before_id JOIN learning_chapters a ON a.id=p.after_id
        WHERE p.version_id=:v AND a.course_id=:c ORDER BY p.after_id,p.before_id''',v=v,c=course_id)
    result['external_requirements']=rows(db,'SELECT * FROM curriculum_external_requirements WHERE version_id=:v AND course_id=:c ORDER BY name',v=v,c=course_id)
    return result


def extend_graph(db,course_id,mappings,graph):
    """Translate explicit local prerequisites; never invent unreviewed mappings."""
    data=structure(db,course_id);mapped={m['skill_id']:m['graph_skill_id'] for m in mappings}
    result={n['id']:{**n,'prerequisites':list(n['prerequisites'])} for n in graph}
    for e in data['skill_prerequisites']:
        if e['kind']!='required' or e['after_id'] not in mapped:continue
        if e['before_id'] not in mapped:fail(409,'请把先修知识点“'+e['before_name']+'”一并映射并选入初测','COURSE_PREREQUISITE_GAP')
        before,after=mapped[e['before_id']],mapped[e['after_id']]
        if before not in result or after not in result:fail(409,'课程映射已不属于当前图谱')
        if before not in result[after]['prerequisites']:result[after]['prerequisites'].append(before)
    try:order=topological_order(result,[{'before_id':p,'after_id':n['id']} for n in result.values() for p in n['prerequisites']])
    except ValueError:fail(409,'课程先修与当前图谱冲突，请管理员核对映射','COURSE_GRAPH_CONFLICT')
    return [result[i] for i in order]
