"""Original, versioned text lessons; external references are not copied as evidence."""
import hashlib,json
from pathlib import Path
from app.core.db import DATA,transaction,one,insert,run,now,dump,audit

ROOT=Path(__file__).resolve().parents[3]

def import_materials():
    pack=json.loads((ROOT/'docs/curriculum/engineering-foundations-lessons.json').read_text(encoding='utf-8'))
    prepared=[]
    for lesson in pack['lessons']:
        body=lesson['body']+'\n\n来源与使用范围：'+pack['license']+'\n参考入口（非转载全文）：\n'+'\n'.join(pack['references'])
        data=body.encode('utf-8');digest=hashlib.sha256(data).hexdigest()
        ident=pack['version']+'-'+lesson['skill_id'];vid=ident+'-v1';storage=digest+'.txt'
        prepared.append((lesson,body,data,digest,ident,vid,storage))
    with transaction() as db:
        admin=one(db,"SELECT id FROM users WHERE role='admin' AND status='active' ORDER BY created_at LIMIT 1")
        if not admin:raise ValueError('需要已有管理员和课程目录')
        # Validate every source before touching any file or business record.
        for lesson,body,data,digest,ident,vid,storage in prepared:
            if not one(db,'SELECT id FROM curriculum_catalog_skills WHERE id=:s',s=lesson['skill_id']):raise ValueError('课程知识点不存在')
            old=one(db,'SELECT hash FROM resource_versions WHERE id=:i',i=vid)
            if old and old['hash']!=digest:raise ValueError('讲义版本内容已改变，需创建新版本')
        created=0
        for lesson,body,data,digest,ident,vid,storage in prepared:
            if one(db,'SELECT id FROM resources WHERE id=:i',i=ident):continue
            skill=one(db,'SELECT * FROM curriculum_catalog_skills WHERE id=:s',s=lesson['skill_id'])
            (DATA/'files'/storage).write_bytes(data)
            insert(db,'resources',id=ident,owner_id=admin['id'],scope='school',title=skill['name']+' · 原创基础讲义',description='工程目标基础阶段学习正文，非官方教材',tags=skill['name']+' C++ OpenGL 图形学',source_license=pack['license'],cloud_allowed=1,kind='text',status='published',current_version=vid,created_at=now())
            insert(db,'resource_versions',id=vid,resource_id=ident,filename=skill['name']+'.txt',storage_key=storage,mime='text/plain',bytes=len(data),hash=digest,body=body,parse_status='ready',index_status='indexed',review_status='approved',extraction_json=dump({'kind':'original_lesson','review':'technical_self_review_not_teacher','references':pack['references']}),created_at=now())
            from app.api.resources import tokenize
            run(db,'INSERT INTO chunks VALUES(:r,:v,:b)',r=ident,v=vid,b=tokenize(body))
            insert(db,'learning_material_links',id=ident,course_id=skill['course_id'],skill_id=skill['id'],resource_id=ident,resource_version_id=vid,locator='基础讲解、练习与自检')
            created+=1
        if created:audit(db,None,'engineering_original_lessons_imported',pack['version'],dump({'created':created,'review':'technical_self_review_not_teacher'}))
    return {'pack':pack['version'],'lessons':len(prepared),'created':created}
