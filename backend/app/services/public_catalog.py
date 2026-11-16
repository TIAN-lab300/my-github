"""Idempotent Chinese reading cards. External source text is not a local exam bank."""
import hashlib,json
from pathlib import Path
from app.core.db import transaction,one,run,insert,now,dump,audit

ROOT=Path(__file__).resolve().parents[3]

def load_catalog():
    base=ROOT/'docs'/'curriculum'
    courses=json.loads((base/'bit-cs-all-years-draft.json').read_text(encoding='utf-8'))['courses']
    catalog=json.loads((base/'public-sources-catalog.json').read_text(encoding='utf-8'))
    sources=catalog['sources']
    if len({c['id'] for c in courses})!=len(courses):raise ValueError('Duplicate course identifiers')
    source_ids={s['id'] for s in sources}
    if len(source_ids)!=len(sources):raise ValueError('Duplicate sources')
    for c in courses:
        if not set(c.get('public_source_candidates',[]))<=source_ids:raise ValueError('Unknown source reference')
    return courses,sources

def chinese_card(source,courses):
    related=[c for c in courses if source['id'] in c.get('public_source_candidates',[])]
    course_text='、'.join(c['name'] for c in related)
    topics='；'.join(source['candidate_topics'].split('、'))
    return '\n\n'.join([
        '【中文资料导读｜外部原文未翻译全文】',
        '资料名称：'+source['title'],
        '资料类型：'+source['kind'],
        '适用课程：'+course_text,
        '主要内容：'+topics+'。',
        '阅读建议：先核对课程知识范围，再按来源目录选择相关章节；学习后自行解释概念，并完成公开练习或编写最小程序验证。',
        '知识点对应（候选，未逐节审核）：'+ '\n'.join(c['name']+'：'+'、'.join(k['name'] for k in c['skills']) for c in related),
        '练习使用说明：来源可能提供编程、证明、计算或设计练习，不能默认按单选题自动评分；答案、解析及重测版本须另行核实。',
        '访问与适用限制：'+source['limitations'],
        '原始内容语言：'+{'zh':'中文','en':'英文','en/zh':'英文；网站另有中文入口'}.get(source['language'],source['language']),
        '原文网址：'+source['url'],
        '状态：已保存中文导读和来源链接；外部全文、视频与题目未批量复制，课程知识点仍待教学大纲审核。',
        '本卡为项目编写的中文概述与阅读提示，不是原资料的逐字翻译或官方中文版本。第三方内容使用条件以来源为准。'
    ])

def import_catalog():
    courses,sources=load_catalog();created=skipped=0
    with transaction() as db:
        admin=one(db,"SELECT id FROM users WHERE role='admin' AND status='active' ORDER BY created_at LIMIT 1")
        if not admin:raise ValueError('需要已有管理员账号，导入不会创建账号')
        for c in courses:
            ident='public-'+c['id']
            if not one(db,'SELECT id FROM curriculum_catalog_courses WHERE id=:i',i=ident):
                insert(db,'curriculum_catalog_courses',id=ident,name=c['name'],year=c.get('year'),category=c['category'],elective=int(c['elective']),assessment_mode=c['assessment_mode'],status='draft',source_basis='用户课程范围；候选知识点，尚非官方核准大纲')
                for k in c['skills']:insert(db,'curriculum_catalog_skills',id='public-'+k['id'],course_id=ident,name=k['name'],status='pending_syllabus_review')
        for s in sources:
            body=chinese_card(s,courses);h=hashlib.sha256(body.encode()).hexdigest()
            existing=one(db,'SELECT * FROM public_source_catalog WHERE id=:i',i=s['id'])
            if existing:
                if existing['import_hash']!=h:raise ValueError('来源已变更，需要显式版本更新：'+s['id'])
                skipped+=1;continue
            rid='public-source-'+s['id'];vid=rid+'-zh-v1'
            names=[c['name'] for c in courses if s['id'] in c.get('public_source_candidates',[])]
            tags='公开资料 中文导读 '+s['candidate_topics']+' '+' '.join(names)
            insert(db,'resources',id=rid,owner_id=admin['id'],class_id=None,scope='school',title='【中文导读】'+s['title'],description='中文概述与阅读建议，外部原文未全文翻译。'+s['limitations'],tags=tags[:500],source_license='项目中文导读；第三方原文仅提供链接，转载与改编需逐项核对来源许可',cloud_allowed=0,kind='link',status='published',current_version=vid,created_at=now())
            # Link metadata deliberately stays out of FTS and vector evidence.
            insert(db,'resource_versions',id=vid,resource_id=rid,filename=s['url'],storage_key=None,mime='text/plain',bytes=0,hash=h,body=body,parse_status='not_applicable',index_status='not_applicable',extraction_json=dump({'kind':'chinese_reading_guide','fulltext_translated':False,'source_id':s['id']}),created_at=now())
            insert(db,'public_source_catalog',id=s['id'],resource_id=rid,url=s['url'],original_language=s['language'],metadata_json=dump(s),import_hash=h,imported_at=now())
            created+=1
        for c in courses:
            for source_id in c.get('public_source_candidates',[]):
                run(db,'INSERT OR IGNORE INTO curriculum_catalog_sources(course_id,source_id) VALUES(:c,:s)',c='public-'+c['id'],s=source_id)
        from app.services.curriculum_search import rebuild
        rebuild(db)
        if created:audit(db,admin['id'],'public_catalog_imported','public-curriculum',dump({'sources':created,'courses':len(courses),'skills':sum(len(c['skills']) for c in courses)}))
    return {'courses':len(courses),'skills':sum(len(c['skills']) for c in courses),'created_sources':created,'skipped_sources':skipped,'questions_imported':0}
