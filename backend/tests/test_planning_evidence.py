import json
from app.core.db import transaction, one
from test_platform import P, classroom, resource, goal, planning, task


def test_diagnostic_evidence_replan_and_isolation(clients):
    cid, _ = classroom(clients)
    resource(clients, cid)
    gid = goal(clients, cid)
    student = clients['student']
    pid = planning(student, gid)
    evidence = student.get(P+'/paths/'+pid).json()['validation']['learner_evidence']
    assert len(evidence['skills']) == 3
    assert all(s['diagnostic_total'] == 2 and s['diagnostic_correct'] == 0 for s in evidence['skills'])
    assert all(s['evidence_count'] == 2 for s in evidence['skills'])
    assert 'answer' not in json.dumps(evidence)
    assert clients['student2'].get(P+'/paths/'+pid).status_code == 404
    assert student.post(P+'/paths/'+pid+'/accept').status_code == 200
    assert not student.get(P+'/goals').json()[0]['requires_replan']
    tid = task(clients, cid)
    assert student.post(P+f'/tasks/{tid}/attempts', json={'answers': {'q3':'1'}, 'minutes':1}).status_code == 200
    listing = student.get(P+'/goals').json()[0]
    assert listing['requires_replan'] and '有效测验证据变化' in listing['replan_reasons']
    candidate = planning(student, gid, replan=True)
    path = student.get(P+'/paths/'+candidate).json()
    assert '有效测验证据变化' in path['validation']['triggers']
    recursion = next(s for s in path['validation']['learner_evidence']['skills'] if s['skill_id']=='recursion')
    assert recursion['evidence_count'] == 3
    assert student.get(P+'/paths/'+pid).json()['status'] == 'active'
    # A later learning write invalidates a preview before activation.
    item = student.get(P+'/paths/'+pid).json()['tasks'][0]
    assert student.post(P+'/check-ins',json={'path_id':pid,'item_id':item['id'],'minutes':1,'proportion':.1,'difficulty':'正常','note':''}).status_code == 200
    assert student.post(P+'/paths/'+candidate+'/accept').status_code == 409


def test_cloud_diagnosis_receives_scored_evidence(clients, monkeypatch):
    from app.services import cloud_planning
    cid, _ = classroom(clients)
    resource(clients, cid)
    gid = goal(clients, cid)
    pid = planning(clients['student'], gid)
    with transaction() as db:
        record = one(db,'SELECT id FROM agent_runs WHERE result_id=:p',p=pid)
    sent = {}
    def capture(state, agent, payload):
        sent.update(payload)
        return {'summary':'基于已评分证据', 'risks':[]}
    monkeypatch.setattr(cloud_planning, 'agent_call', capture)
    monkeypatch.setattr(cloud_planning.planning, 'record_cloud_step', lambda *args: None)
    cloud_planning.diagnose({'run_id':record['id'], 'cloud_mode':True})
    assert sent['learner_evidence']['attempt_id']
    assert all(s['diagnostic_correct']==0 for s in sent['learner_evidence']['skills'])
    assert 'budget' in sent
    assert not {'password_hash','username','answers'} & sent.keys()
