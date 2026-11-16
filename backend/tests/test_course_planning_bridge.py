from datetime import datetime,timedelta,timezone
import json
import pytest
from app.core.db import transaction,one,rows,insert,run,now
from app.services.public_catalog import import_catalog
from test_platform import P,planning


@pytest.fixture
def course_bank(clients):
    import_catalog();admin=clients['admin'];cid='public-C01'
    skills=[cid+'-K00'+str(n) for n in range(1,4)]
    graph=['functions','recursion','stack'];versions={}
    with transaction() as db:
        # These are teaching fixtures, not claims about the imported syllabus.
        run(db,'UPDATE curriculum_catalog_courses SET name=:n WHERE id=:c',n='验收样例：函数与递归',c=cid)
        for sid,name in zip(skills,['函数基础','递归与结束条件','调用栈与综合练习']):
            run(db,'UPDATE curriculum_catalog_skills SET name=:n WHERE id=:s',n=name,s=sid)
        insert(db,'resources',id='course-body',owner_id='admin',scope='school',title='函数递归正文',description='测试',tags='函数',source_license='测试原创',cloud_allowed=1,kind='text',status='published',current_version='course-v1',created_at=now())
        insert(db,'resource_versions',id='course-v1',resource_id='course-body',filename='course.txt',bytes=100,hash='fixture',body='函数 function def return。递归 recursion 必须趋向基本情况。调用栈 stack 后进先出。',parse_status='ready',index_status='indexed',created_at=now())
    for sid,g in zip(skills,graph):
        r=admin.post(P+f'/learning/courses/{cid}/planning-mappings',json={'skill_id':sid,'graph_skill_id':g,'graph_version':'curated-v1','confirmed':True})
        assert r.status_code==201,r.text
        assert admin.post(P+f'/learning/courses/{cid}/materials',json={'skill_id':sid,'resource_id':'course-body'}).status_code==201
        for phase in ('diagnostic','practice','retest'):
            for n in range(2):
                q=admin.post(P+'/learning/questions',json={'course_id':cid,'skill_id':sid,'phase':phase,'prompt':f'{g} {phase} 第{n}题','options':['正确','错误'],'answer':0,'explanation':'原创测试解析','source':'隔离测试原创'})
                assert q.status_code==201,q.text
                vid=q.json()['id'];versions[(g,phase,n)]=vid
                assert admin.post(P+'/learning/questions/'+vid+'/publish',json={'confirmed':True}).status_code==200
    return cid,skills,versions


def paper(student,cid,skills,phase='diagnostic',answer=1):
    r=student.post(P+'/learning/assessments',json={'course_id':cid,'skill_ids':skills,'phase':phase,'per_skill':2})
    assert r.status_code==201,r.text
    ident=r.json()['id'];p=student.get(P+'/learning/assessments/'+ident).json()
    answers={q['id']:answer for q in p['questions']}
    assert student.post(P+'/learning/assessments/'+ident+'/submit',json={'answers':answers}).status_code==200
    return ident,answers


def connect(student,cid,assessment):
    return student.post(P+f'/learning/courses/{cid}/goals',json={'assessment_id':assessment,'title':'课程补强目标','weekly_minutes':300,'due_date':(datetime.now(timezone.utc)+timedelta(days=20)).date().isoformat()})


def test_course_initial_plan_retest_and_replanning(clients,course_bank):
    cid,skills,versions=course_bank;s=clients['student']
    aid,answers=paper(s,cid,skills)
    r=connect(s,cid,aid);assert r.status_code==201,r.text
    gid=r.json()['id'];assert connect(s,cid,aid).json()['id']==gid
    with transaction() as db:
        assert one(db,'SELECT COUNT(*) n FROM learning_evidence_links')['n']==6
        assert one(db,'SELECT COUNT(*) n FROM observations')['n']==6
    assert clients['student2'].get(P+'/diagnoses/'+r.json()['diagnosis_id']).status_code==404
    pid=planning(s,gid);p=s.get(P+'/paths/'+pid).json()
    assert p['validation']['learner_evidence']['catalog_evidence_integrated']
    assert s.post(P+'/paths/'+pid+'/accept').status_code==200
    item=next(t for t in p['tasks'] if t['skill_id']=='functions')
    session=s.get(P+f"/paths/{pid}/items/{item['id']}/assessment").json()
    assert session['questions'][0]['id'] in versions.values()
    q=session['questions'][0]
    response=s.post(P+'/assessment-sessions/'+session['id']+'/submit',json={'answers':{q['id']:'1'},'minutes':1})
    assert response.status_code==200,response.text
    repeat=s.post(P+f"/paths/{pid}/items/{item['id']}/retests")
    assert repeat.status_code==200,repeat.text
    second=repeat.json();assert second['questions'][0]['id']!=q['id']
    assert second['questions'][0]['id'] in [versions[('functions','retest',n)] for n in range(2)]
    assert s.post(P+'/learning/assessments/'+aid+'/submit',json={'answers':answers}).status_code==200
    with transaction() as db:assert one(db,'SELECT COUNT(*) n FROM learning_evidence_links')['n']==6
    # A course practice assessment synchronizes fresh mapped evidence once.
    practice,_=paper(s,cid,[skills[1]],'practice',0)
    with transaction() as db:assert one(db,'SELECT COUNT(*) n FROM learning_evidence_links')['n']==8
    assert s.get(P+'/goals').json()[0]['requires_replan']
    next_path=planning(s,gid,True)
    assert '有效测验证据变化' in s.get(P+'/paths/'+next_path).json()['validation']['triggers']
    assert s.get(P+'/paths/'+pid).json()['status']=='active'
    # Retiring even an unused course bank version invalidates generated previews.
    clients['admin'].post(P+'/learning/questions/'+versions[('stack','retest',0)]+'/disable')
    assert s.post(P+'/paths/'+next_path+'/accept').status_code==409


def test_mapping_permissions_version_and_prerequisites(clients,course_bank):
    cid,skills,_=course_bank;s=clients['student']
    body={'skill_id':skills[0],'graph_skill_id':'functions','graph_version':'curated-v1','confirmed':True}
    assert s.post(P+f'/learning/courses/{cid}/planning-mappings',json=body).status_code==403
    body['graph_version']='stale'
    assert clients['admin'].post(P+f'/learning/courses/{cid}/planning-mappings',json=body).status_code==409
    aid,_=paper(s,cid,[skills[1]])
    assert connect(s,cid,aid).status_code==409
    assert connect(clients['student2'],cid,aid).status_code==404
    with transaction() as db:assert not rows(db,'SELECT * FROM course_goal_bindings')


def test_course_disabled_question_and_graph_change(clients,course_bank):
    cid,skills,versions=course_bank;s=clients['student']
    aid,_=paper(s,cid,skills);gid=connect(s,cid,aid).json()['id']
    pid=planning(s,gid);s.post(P+'/paths/'+pid+'/accept')
    item=s.get(P+'/paths/'+pid).json()['tasks'][0]
    session=s.get(P+f"/paths/{pid}/items/{item['id']}/assessment").json();q=session['questions'][0]
    clients['admin'].post(P+'/learning/questions/'+q['id']+'/disable')
    assert s.post(P+'/assessment-sessions/'+session['id']+'/submit',json={'answers':{q['id']:'0'},'minutes':1}).status_code==409
    with transaction() as db:
        before=one(db,'SELECT COUNT(*) n FROM observations')['n']
        insert(db,'graph_versions',id='changed',nodes='[]',edges='[]',active=1,created_at=now())
    assert s.get(P+f"/paths/{pid}/items/{item['id']}/assessment").status_code==409
    with transaction() as db:assert one(db,'SELECT COUNT(*) n FROM observations')['n']==before


def test_goal_revision_reuses_evidence_without_replay(clients,course_bank):
    cid,skills,_=course_bank;s=clients['student']
    aid,_=paper(s,cid,skills);gid=connect(s,cid,aid).json()['id']
    assert s.patch(P+'/goals/'+gid,json={'version':1,'title':'修改期限说明'}).status_code==200
    assert s.get(P+'/goals').json()[0]['requires_diagnosis']
    r=s.post(P+f'/goals/{gid}/diagnoses');assert r.status_code==201,r.text
    assert r.json()['attempt_id']
    with transaction() as db:assert one(db,'SELECT COUNT(*) n FROM observations')['n']==6
    assert s.patch(P+'/goals/'+gid,json={'version':2,'target_skill_ids':['functions']}).status_code==409


def test_course_reading_invalidates_preview_without_mastery_change(clients,course_bank):
    cid,skills,_=course_bank;s=clients['student']
    aid,_=paper(s,cid,skills);gid=connect(s,cid,aid).json()['id']
    pid=planning(s,gid);assert s.post(P+'/paths/'+pid+'/accept').status_code==200
    preview=planning(s,gid,True)
    with transaction() as db:
        before=one(db,'SELECT COUNT(*) n FROM observations')['n']
        link=one(db,'SELECT id FROM learning_material_links WHERE skill_id=:s',s=skills[0])['id']
    assert s.post(P+f'/learning/materials/{link}/study',json={'session_id':'reading-once','minutes':10}).status_code==200
    assert s.post(P+'/paths/'+preview+'/accept').status_code==409
    assert '学习执行记录变化' in s.get(P+'/goals').json()[0]['replan_reasons']
    with transaction() as db:
        assert one(db,'SELECT COUNT(*) n FROM observations')['n']==before
        from app.services.learning import actual_events
        assert sum(e['minutes'] for e in actual_events(db,'student'))==10
