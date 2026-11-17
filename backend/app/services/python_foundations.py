"""Idempotent project-authored Python lessons and assessment pack, not an official syllabus."""
import hashlib,json
from pathlib import Path
from app.core.db import DATA,transaction,one,rows,insert,run,now,dump,audit
ROOT=Path(__file__).resolve().parents[3]/'docs/curriculum/python-foundations'

def load_pack():
    raw=(ROOT/'pack.json').read_bytes();pack=json.loads(raw);lessons={}
    ids={s['id'] for s in pack['skills']};seen=set();prompts=set();counts={}
    for s in pack['skills']:
        path=(ROOT/s['lesson']).resolve()
        if path.parent!=ROOT.resolve():raise ValueError('Lesson path outside pack')
        text=path.read_text(encoding='utf-8')
        if len(text)<500 or not set(s['prerequisites'])<=ids:raise ValueError('Incomplete lesson or prerequisite')
        lessons[s['id']]=text
    for q in pack['questions']:
        if q['id'] in seen or q['prompt'] in prompts or q['skill_id'] not in ids:raise ValueError('Duplicate or unmapped question')
        if q['phase'] not in ('diagnostic','practice','retest') or not 2<=len(q['options'])<=8 or type(q['answer']) is not int or not 0<=q['answer']<len(q['options']) or not q['explanation'].strip():raise ValueError('Invalid question')
        seen.add(q['id']);prompts.add(q['prompt']);key=(q['skill_id'],q['phase']);counts[key]=counts.get(key,0)+1
    if len(ids)!=3 or len(seen)!=36 or any(counts.get((s,p))!=4 for s in ids for p in ('diagnostic','practice','retest')):raise ValueError('Expected 3 skills and 36 questions')
    digest=hashlib.sha256(raw+dump(lessons).encode()).hexdigest()
    return pack,lessons,digest

def import_pack():
    pack,lessons,digest=load_pack();version=pack['version'];cid=pack['course_id'];created_files=[]
    try:
        with transaction() as db:
            old=one(db,'SELECT * FROM learning_bank_releases WHERE id=:v',v=version)
            if old:
                if old['content_hash']!=digest:raise ValueError('Pack changed: create a new immutable version')
                return {'release':version,'course_id':cid,'already_imported':True,'created_questions':0}
            admin=one(db,"SELECT id FROM users WHERE role='admin' AND status='active' ORDER BY created_at,id LIMIT 1")
            if not admin:raise ValueError('Existing administrator required')
            if one(db,'SELECT id FROM curriculum_catalog_courses WHERE id=:c',c=cid):raise ValueError('Course identity already exists outside this release')
            for s in pack['skills']:
                if one(db,'SELECT id FROM curriculum_graph_mappings WHERE graph_skill_id=:g',g=s['graph_skill_id']):raise ValueError('Legacy skill mapping already assigned; manual review required')
            insert(db,'curriculum_catalog_courses',id=cid,name=pack['name'],year=None,category='项目补充课程',elective=1,assessment_mode='single_choice',status='published',source_basis=pack['provenance'])
            insert(db,'learning_bank_releases',id=version,content_hash=digest,provenance=pack['provenance'],review_kind=pack['review'],created_at=now())
            for index,s in enumerate(pack['skills']):
                sid=s['id'];body=lessons[sid];data=body.encode();h=hashlib.sha256(data).hexdigest();rid=version+'-'+s['graph_skill_id'];vid=rid+'-body-v1';storage='python-pack-'+h+'.md';target=DATA/'files'/storage
                if target.exists():
                    if target.read_bytes()!=data:raise ValueError('Storage hash mismatch')
                else:target.write_bytes(data);created_files.append(target)
                insert(db,'curriculum_catalog_skills',id=sid,course_id=cid,name=s['name'],status='project_technical_checked')
                insert(db,'learning_chapters',id=s['chapter_id'],course_id=cid,title=s['name'],position=index)
                insert(db,'learning_skill_chapters',skill_id=sid,chapter_id=s['chapter_id'],course_id=cid)
                insert(db,'resources',id=rid,owner_id=admin['id'],scope='school',title='Python '+s['name']+' · 项目原创讲义',description=pack['provenance']+'；'+pack['review'],tags='Python 函数 def return 参数 递归 调用栈 '+s['name'],source_license='项目原创教学资料，允许本项目教学使用；第三方文档仅作参考链接',cloud_allowed=1,kind='text',status='published',current_version=vid,created_at=now())
                insert(db,'resource_versions',id=vid,resource_id=rid,filename=s['lesson'],storage_key=storage,mime='text/markdown',bytes=len(data),hash=h,body=body,parse_status='ready',index_status='indexed',review_status='not_required',extraction_json=dump({'release':version,'technical_review':True,'teacher_approved':False,'language':'Python 3'}),created_at=now())
                from app.api.resources import tokenize
                run(db,'INSERT INTO chunks(resource_id,version_id,body) VALUES(:r,:v,:b)',r=rid,v=vid,b=tokenize(body))
                insert(db,'learning_material_links',id=rid+'-link',course_id=cid,skill_id=sid,resource_id=rid,resource_version_id=vid,locator='原创讲义全文；按章节阅读')
                insert(db,'curriculum_graph_mappings',id=rid+'-mapping',course_id=cid,skill_id=sid,graph_version='curated-v1',graph_skill_id=s['graph_skill_id'],reviewer_id=admin['id'],created_at=now())
            for q in pack['questions']:
                insert(db,'learning_questions',id=q['id'],course_id=cid,owner_id=admin['id'],created_at=now())
                vid=q['id']+'-v1'
                insert(db,'learning_question_versions',id=vid,question_id=q['id'],course_id=cid,skill_id=q['skill_id'],version=1,phase=q['phase'],prompt=q['prompt'],options=dump(q['options']),answer=q['answer'],explanation=q['explanation'],source=q['source'],status='published',reviewer_id=None,created_at=now())
                insert(db,'learning_bank_release_items',release_id=version,question_version_id=vid)
            # Extend prerequisite relations in a new version; prior snapshots stay intact.
            active=one(db,'SELECT * FROM curriculum_relation_versions WHERE active=1');relation_id=version+'-relations'
            tables={'curriculum_course_prerequisites':['before_id','after_id','kind','reason'],'curriculum_skill_prerequisites':['before_id','after_id','kind','reason'],'curriculum_chapter_prerequisites':['before_id','after_id','kind','reason'],'curriculum_external_requirements':['course_id','name','kind','reason']}
            inherited={table:rows(db,'SELECT '+','.join(cols)+' FROM '+table+' WHERE version_id=:v',v=active['id']) if active else [] for table,cols in tables.items()}
            for index,s in enumerate(pack['skills'][1:],1):
                previous=pack['skills'][index-1]
                for table,before,after in [('curriculum_skill_prerequisites',previous['id'],s['id']),('curriculum_chapter_prerequisites',previous['chapter_id'],s['chapter_id'])]:inherited[table].append({'before_id':before,'after_id':after,'kind':'required','reason':'先理解Python函数，再理解递归及调用返回过程；项目技术编排，非官方教学大纲'})
            insert(db,'curriculum_relation_versions',id=relation_id,payload_hash=hashlib.sha256(dump(inherited).encode()).hexdigest(),basis='继承原先修关系并增加Python项目补充课程；'+pack['review'],official_verified=0,active=0,created_at=now())
            for table,entries in inherited.items():
                for entry in entries:insert(db,table,version_id=relation_id,**entry)
            run(db,'UPDATE curriculum_relation_versions SET active=0 WHERE active=1');run(db,'UPDATE curriculum_relation_versions SET active=1 WHERE id=:v',v=relation_id)
            from app.services.curriculum_search import rebuild
            rebuild(db)
            audit(db,None,'python_foundations_imported',version,dump({'course':cid,'skills':3,'lessons':3,'questions':36,'review_kind':pack['review'],'teacher_approved':False,'legacy_mapping_basis':'技术核对Python同一语言同一能力，非名称猜测'}))
        return {'release':version,'course_id':cid,'created_skills':3,'created_lessons':3,'created_questions':36,'already_imported':False}
    except Exception:
        for path in created_files:path.unlink(missing_ok=True)
        raise
