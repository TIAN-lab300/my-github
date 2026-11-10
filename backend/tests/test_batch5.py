from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
import json,hashlib,sqlite3
import pytest
from app.core.db import transaction,one,rows,run,uid,now,DATA
from app.services.learning import QUESTIONS
from test_platform import P,classroom,resource,goal,planning,task
import test_platform as existing

IDS=[f'SF-PATH-{i:02}' for i in range(1,10)]+[f'SF-REPLAN-{i:02}' for i in range(1,8)]+['SF-AI-05','SF-AI-07','SF-OPS-04','SF-OPS-05']

def active_path(clients):
    cid,_=classroom(clients);rid=resource(clients,cid);gid=goal(clients,cid)
    student=clients['student'];pid=planning(student,gid)
    assert student.post(P+'/paths/'+pid+'/accept').status_code==200
    return cid,rid,gid,pid

def correct_functions(clients,cid):
    teacher=clients['teacher'];student=clients['student']
    for _ in range(3):
        body={'class_id':cid,'title':'函数补强','description':'练习','due_at':(datetime.now(timezone.utc)+timedelta(days=2)).isoformat(),'minutes':1,'questions':[QUESTIONS[0]]}
        tid=teacher.post(P+'/teacher/tasks',json=body).json()['id']
        teacher.post(P+f'/teacher/tasks/{tid}/publish')
        assert student.post(P+f'/tasks/{tid}/attempts',json={'answers':{'q1':'0'},'minutes':1}).status_code==200

def candidate_state(pid):
    with transaction() as db:
        record=one(db,'SELECT checkpoint FROM agent_runs WHERE result_id=:p',p=pid)
    return json.loads(record['checkpoint'])

@pytest.mark.parametrize('sf',IDS)
def test_batch5(sf,clients,monkeypatch,tmp_path):
    student=clients['student'];teacher=clients['teacher'];admin=clients['admin']
    if sf=='SF-PATH-01':
        nodes=[{'id':'functions','minutes':35},{'id':'recursion','minutes':45},{'id':'stack','minutes':45}]
        edges=[['functions','recursion'],['recursion','stack']]
        assert admin.post(P+'/admin/graphs',json={'nodes':nodes,'edges':edges+[['stack','functions']]}).status_code==422
        assert admin.post(P+'/admin/graphs',json={'nodes':[{'id':[],'minutes':1}],'edges':[]}).status_code==422
        graph=admin.post(P+'/admin/graphs',json={'nodes':nodes,'edges':edges}).json()['id']
        assert teacher.post(P+'/admin/graphs/'+graph+'/activate').status_code==403
        assert admin.post(P+'/admin/graphs/'+graph+'/activate').status_code==200
        cid,_=classroom(clients);resource(clients,cid);gid=goal(clients,cid);pid=planning(student,gid)
        assert student.get(P+'/paths/'+pid).json()['validation']['graph_version']==graph
        assert student.get(P+'/goals/'+gid+'/feasibility').json()['required_minutes']==125
    elif sf=='SF-PATH-02':
        cid,_=classroom(clients);gid=goal(clients,cid)
        created=student.post(P+f'/goals/{gid}/planning-runs',headers={'Idempotency-Key':'failure'})
        rid=created.json()['run_id'];failed=student.get(P+'/runs/'+rid).json()
        assert failed['status']=='failed' and failed['error']
        resource(clients,cid)
        assert student.post(P+'/runs/'+rid+'/retry').status_code==202
        recovered=student.get(P+'/runs/'+rid).json()
        assert recovered['status']=='succeeded' and recovered['retry_count']==1
        assert student.get(P+f'/goals/{gid}/runs').json()[0]['id']==rid
        assert clients['student2'].get(P+'/runs/'+rid).status_code==404
    elif sf=='SF-PATH-03':
        cid,_=classroom(clients);resource(clients,cid);gid=goal(clients,cid);pid=planning(student,gid)
        with transaction() as db:
            assert not rows(db,'SELECT id FROM reservations WHERE goal_id=:g',g=gid)
            run(db,"UPDATE paths SET content_status='draft' WHERE id=:p",p=pid)
        assert student.post(P+'/paths/'+pid+'/accept').status_code==409
    elif sf=='SF-PATH-04':
        cid,_=classroom(clients);resource(clients,cid);gid=goal(clients,cid)
        correct_functions(clients,cid)
        pid=planning(student,gid)
        path=student.get(P+'/paths/'+pid).json()
        assert [i['skill_id'] for i in path['tasks']]==['recursion','stack']
        assert path['validation']['rules'][0]['passed']
    elif sf=='SF-PATH-05':
        cid,_=classroom(clients);resource(clients,cid);gid=goal(clients,cid)
        settings=student.get(P+'/learners/me/budget').json()
        student.patch(P+'/learners/me/budget',json={**settings,'daily_minutes':20,'weekly_minutes':80})
        pid=planning(student,gid)
        path=student.get(P+'/paths/'+pid).json()
        assert sum(d['minutes'] for d in path['validation']['schedule'])==120
        assert all(type(d['minutes']) is int and d['minutes']<=20 for d in path['validation']['schedule'])
        assert sum(sum(d['minutes'] for d in item['dates']) for item in path['tasks'])==120
    elif sf=='SF-PATH-06':
        from app.services.planning_rules import validate
        cid,_=classroom(clients);resource(clients,cid);gid=goal(clients,cid);pid=planning(student,gid)
        state=candidate_state(pid)
        with transaction() as db:
            assert len(validate(state,db))==8 and all(r['passed'] for r in validate(state,db))
            state['execution']=list(reversed(state['execution']))
            assert not validate(state,db)[0]['passed']
            state['sources']=[]
            assert not validate(state,db)[4]['passed']
    elif sf=='SF-PATH-07':
        cid,_=classroom(clients);rid=resource(clients,cid);gid=goal(clients,cid);pid=planning(student,gid)
        path=student.get(P+'/paths/'+pid).json();source=path['sources'][0]
        assert source['locations'] and source['excerpt'] and path['reason']
        body=teacher.get(P+'/resources/'+rid).json()['body']
        for location in source['locations']:
            assert body[location['start']:location['end']] in source['excerpt']
        assert all(item['assessment'] and item['citations'] for item in path['tasks'])
    elif sf=='SF-PATH-08':
        cid,rid,gid,pid=active_path(clients)
        candidate=planning(student,gid,True)
        assert student.post(P+'/paths/'+candidate+'/accept').status_code==200
        assert student.get(P+'/paths/'+pid).json()['status']=='superseded'
        assert student.post(P+'/paths/'+candidate+'/accept').status_code==200
        with transaction() as db:assert len(rows(db,"SELECT id FROM paths WHERE goal_id=:g AND status='active'",g=gid))==1
    elif sf=='SF-PATH-09':
        cid,rid,gid,pid=active_path(clients)
        original=student.get(P+'/paths/'+pid).json()
        second=original['tasks'][1]['id']
        assert student.post(P+'/check-ins',json={'path_id':pid,'item_id':second,'minutes':5,'proportion':1}).status_code==409
        first=original['tasks'][0]['id']
        student.post(P+'/check-ins',json={'path_id':pid,'item_id':first,'minutes':5,'proportion':1})
        assert student.get(P+'/paths/'+pid).json()['tasks'][1]['locked']
        correct_functions(clients,cid)
        assert not student.get(P+'/paths/'+pid).json()['tasks'][1]['locked']
    elif sf=='SF-REPLAN-01':
        cid,rid,gid,pid=active_path(clients)
        for _ in range(2):
            tid=task(clients,cid)
            with transaction() as db:run(db,"UPDATE tasks SET due_at='2000-01-01T00:00:00+00:00' WHERE id=:id",id=tid)
        candidate=planning(student,gid,True);triggers=student.get(P+'/paths/'+candidate).json()['validation']['triggers']
        assert '掌握薄弱' in triggers and '连续至少两个任务到期未完成' in triggers
    elif sf=='SF-REPLAN-02':
        cid,rid,gid,pid=active_path(clients)
        candidate=planning(student,gid,True)
        assert student.get(P+'/paths/'+candidate).json()['validation']['mode']=='local'
        settings=student.get(P+'/learners/me/budget').json()
        student.patch(P+'/learners/me/budget',json={**settings,'daily_minutes':settings['daily_minutes']*2})
        candidate=planning(student,gid,True)
        assert student.get(P+'/paths/'+candidate).json()['validation']['mode']=='global'
    elif sf=='SF-REPLAN-03':
        cid,rid,gid,pid=active_path(clients);candidate=planning(student,gid,True)
        metadata=student.get(P+'/paths/'+candidate).json()['validation']
        assert all(k in metadata['diff'] for k in ['added','removed','kept','reinforced','before_schedule','after_schedule','risks'])
        assert len(metadata['rules'])==8 and metadata['triggers']
    elif sf=='SF-REPLAN-04':
        cid,rid,gid,pid=active_path(clients)
        other=goal(clients,cid);otherpath=planning(student,other);student.post(P+'/paths/'+otherpath+'/accept')
        with transaction() as db:
            before=rows(db,'SELECT * FROM reservations WHERE goal_id=:g ORDER BY id',g=other)
            own=one(db,'SELECT id FROM reservations WHERE goal_id=:g LIMIT 1',g=gid)
            run(db,"UPDATE reservations SET status='completed' WHERE id=:id",id=own['id'])
        candidate=planning(student,gid,True);assert student.post(P+'/paths/'+candidate+'/accept').status_code==200
        with transaction() as db:
            assert rows(db,'SELECT * FROM reservations WHERE goal_id=:g ORDER BY id',g=other)==before
            assert one(db,'SELECT status FROM reservations WHERE id=:id',id=own['id'])['status']=='completed'
    elif sf=='SF-REPLAN-05':
        cid,rid,gid,pid=active_path(clients);candidate=planning(student,gid,True)
        with transaction() as db:before=rows(db,'SELECT * FROM reservations WHERE goal_id=:g ORDER BY id',g=gid)
        assert student.post(P+'/paths/'+candidate+'/reject').status_code==200
        active=student.get(P+'/paths/'+pid).json()
        assert active['status']=='active' and active['replan_warnings']
        with transaction() as db:assert rows(db,'SELECT * FROM reservations WHERE goal_id=:g ORDER BY id',g=gid)==before
    elif sf=='SF-REPLAN-06':
        cid,rid,gid,pid=active_path(clients);candidate=planning(student,gid,True)
        teacher.post(P+'/resources/'+rid+'/withdraw')
        assert student.post(P+'/paths/'+candidate+'/accept').status_code in (404,409)
        assert student.get(P+'/paths/'+pid).json()['status']=='active'
    elif sf=='SF-REPLAN-07':
        cid,rid,gid,pid=active_path(clients)
        old=student.get(P+'/paths/'+pid).json();item=old['tasks'][0]
        student.post(P+'/check-ins',json={'path_id':pid,'item_id':item['id'],'minutes':5,'proportion':1})
        candidate=planning(student,gid,True);path=student.get(P+'/paths/'+candidate).json()
        assert item['skill_id'] not in [t['skill_id'] for t in path['tasks']]
        assert path['remediations'][0]['source_item_id']==item['id']
        assert path['validation']['preserved'][0]['item']['id']==item['id']
        assert student.post(P+'/paths/'+candidate+'/accept').status_code==200
        reinforcement=student.get(P+'/paths/'+candidate).json()['remediations'][0]
        assert student.post(P+'/check-ins',json={'path_id':candidate,'item_id':reinforcement['id'],'minutes':5,'proportion':1}).status_code==200
        assert student.get(P+f"/paths/{candidate}/items/{reinforcement['id']}/assessment").status_code==200
        assert student.get(P+'/paths/'+pid).json()['tasks'][0]['checkin']['minutes']==5
    elif sf=='SF-AI-05':
        cid,_=classroom(clients);resource(clients,cid);gid=goal(clients,cid);pid=planning(student,gid)
        with transaction() as db:rid=one(db,'SELECT id FROM agent_runs WHERE result_id=:p',p=pid)['id']
        trace=student.get(P+'/runs/'+rid).json()
        assert len(trace['steps'])==4
        assert all(step['input_fingerprint'] and step['output_summary'] and step['created_at'] for step in trace['steps'])
        assert trace['checkpoint']['last_agent']=='LearningReplanAgent'
        assert 'password_hash' not in json.dumps(trace) and 'state' not in trace['checkpoint']
    elif sf=='SF-AI-07':
        from app.services import planning as service
        cid,_=classroom(clients);resource(clients,cid);gid=goal(clients,cid)
        original=service.validate
        def interrupted(*args):raise RuntimeError('injected interruption')
        monkeypatch.setattr(service,'validate',interrupted)
        failed=student.post(P+f'/goals/{gid}/planning-runs',headers={'Idempotency-Key':'checkpoint'})
        rid=failed.json()['run_id'];trace=student.get(P+'/runs/'+rid).json()
        assert trace['status']=='failed' and trace['checkpoint']['last_agent']=='PathBuildingAgent'
        monkeypatch.setattr(service,'validate',original)
        assert student.post(P+'/runs/'+rid+'/retry').status_code==202
        trace=student.get(P+'/runs/'+rid).json()
        assert trace['status']=='succeeded' and len([s for s in trace['steps'] if s['agent']=='GoalDiagnosisAgent'])==1
        with transaction() as db:
            cancel_id=uid();insert_values={'id':cancel_id,'actor_id':'student','goal_id':gid,'kind':'initial','status':'queued','idem_key':'cancel','created_at':now()}
            from app.core.db import insert
            insert(db,'agent_runs',**insert_values)
        assert student.post(P+'/runs/'+cancel_id+'/cancel').status_code==200
        service.execute(cancel_id)
        assert student.get(P+'/runs/'+cancel_id).json()['status']=='cancelled'
        assert student.post(P+'/runs/'+cancel_id+'/retry').status_code==409
    elif sf in ('SF-OPS-04','SF-OPS-05'):
        from app.cli import backup,restore,rebuild_index
        monkeypatch.setenv('BACKUP_TEST_SECRET','never-include-this-value')
        assert admin.post(P+'/admin/model-configs',json={'model':'qwen-plus','secret_env':'BACKUP_TEST_SECRET'}).status_code==201
        cid,_=classroom(clients);rid=resource(clients,cid)
        destination=tmp_path/'backup';restored=tmp_path/'restored'
        backup(destination)
        manifest=json.loads((destination/'manifest.json').read_text(encoding='utf-8'))
        with transaction() as db:expected_revision=one(db,'SELECT version_num FROM alembic_version')['version_num']
        assert manifest['schema_revision']==expected_revision and manifest['record_counts']['resources']==1
        assert manifest['database_sha256']==hashlib.sha256((destination/'zhixing.db').read_bytes()).hexdigest()
        assert manifest['config_references'][0]['secret_env']=='BACKUP_TEST_SECRET'
        assert 'never-include-this-value' not in (destination/'manifest.json').read_text(encoding='utf-8')
        restore(destination,restored)
        rebuild_index(restored)
        restored_manifest=json.loads((restored/'manifest.json').read_text(encoding='utf-8'))
        assert restored_manifest['database_sha256']==hashlib.sha256((restored/'zhixing.db').read_bytes()).hexdigest()
        with sqlite3.connect(restored/'zhixing.db') as db:
            assert db.execute('PRAGMA foreign_key_check').fetchall()==[]
            assert db.execute("SELECT count(*) FROM chunks WHERE chunks MATCH 'recursion'").fetchone()[0]>0
        with pytest.raises(SystemExit):restore(destination,restored)
        filename=next(iter(manifest['files']))
        (destination/'files'/filename).write_bytes(b'changed')
        rejected=tmp_path/'rejected'
        with pytest.raises(SystemExit):restore(destination,rejected)
        assert not rejected.exists()

def test_local_failure_falls_back_to_remaining_work_global_schedule(clients):
    student=clients['student']
    cid,_=classroom(clients);resource(clients,cid)
    settings=student.get(P+'/learners/me/budget').json()
    student.patch(P+'/learners/me/budget',json={**settings,'daily_minutes':35})
    today=datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()
    created=student.post(P+'/goals',json={'title':'函数','target_skill_ids':['functions'],'weekly_minutes':300,'due_date':today,'class_id':cid})
    gid=created.json()['id']
    d=student.post(P+f'/goals/{gid}/diagnoses').json()
    answer={q['id']:str((int(q['answer'])+1)%len(q['options'])) for q in QUESTIONS}
    student.post(P+'/diagnoses/'+d['id']+'/submit',json={'answers':answer,'minutes':5})
    pid=planning(student,gid);student.post(P+'/paths/'+pid+'/accept')
    item=student.get(P+'/paths/'+pid).json()['tasks'][0]
    student.post(P+'/check-ins',json={'path_id':pid,'item_id':item['id'],'minutes':5,'proportion':.5})
    settings=student.get(P+'/learners/me/budget').json()
    student.patch(P+'/learners/me/budget',json={**settings,'daily_minutes':25})
    candidate=planning(student,gid,True)
    state=student.get(P+'/paths/'+candidate).json()
    assert state['validation']['mode']=='global'
    assert '局部排期不可行，改为全局重排' in state['validation']['triggers']
    assert state['tasks'][0]['minutes']==15

def test_cancel_after_build_prevents_final_commit(clients,monkeypatch):
    from app.services import planning as service
    cid,_=classroom(clients);resource(clients,cid);gid=goal(clients,cid)
    original=service.step
    def cancel_at_build(state,agent,detail):
        if agent=='PathBuildingAgent':
            with transaction() as db:
                run(db,"UPDATE agent_runs SET status='cancelled' WHERE id=:id",id=state['run_id'])
        return original(state,agent,detail)
    monkeypatch.setattr(service,'step',cancel_at_build)
    result=clients['student'].post(P+f'/goals/{gid}/planning-runs',headers={'Idempotency-Key':'mid-cancel'})
    trace=clients['student'].get(P+'/runs/'+result.json()['run_id']).json()
    assert trace['status']=='cancelled' and trace['result_id'] is None
    with transaction() as db:
        assert not rows(db,'SELECT id FROM paths WHERE goal_id=:g',g=gid)
        assert not rows(db,'SELECT id FROM reservations WHERE goal_id=:g',g=gid)

def test_backup_database_hash_and_manifest_counts_are_verified(clients,tmp_path):
    from app.cli import backup,restore
    cid,_=classroom(clients);resource(clients,cid)
    directory=tmp_path/'backup';backup(directory)
    database=directory/'zhixing.db'
    content=bytearray(database.read_bytes());content[-1]^=1;database.write_bytes(content)
    with pytest.raises(SystemExit,match='哈希'):restore(directory,tmp_path/'invalid')
    assert not (tmp_path/'invalid').exists()

def test_membership_change_invalidates_pending_preview(clients):
    cid,rid,gid,pid=active_path(clients);student=clients['student']
    candidate=planning(student,gid,True)
    assert clients['teacher'].delete(P+f'/classes/{cid}/members/student').status_code==200
    response=student.post(P+'/paths/'+candidate+'/accept')
    assert response.status_code==409 and response.json()['code']=='STALE_PREVIEW'
    assert student.get(P+'/paths/'+pid).json()['status']=='active'
