import json
import pytest
from test_platform import P,planning
from test_batch5 import active_path
from app.core.db import transaction,one,run

def setup_item(clients):
    _,_,gid,pid=active_path(clients)
    item=clients['student'].get(P+'/paths/'+pid).json()['tasks'][0]
    return gid,pid,item

def reserved(pid):
    with transaction() as db:return one(db,'SELECT SUM(minutes) AS n FROM reservations WHERE source_id=:p AND status=\'active\'',p=pid)['n']

def test_incremental_progress_is_idempotent(clients):
    gid,pid,item=setup_item(clients);s=clients['student'];before=reserved(pid)
    payload={'path_id':pid,'item_id':item['id'],'minutes':10,'proportion':.5}
    assert s.post(P+'/check-ins',json=payload).status_code==200
    half=reserved(pid)
    assert half==before-int(item['minutes']*.5)
    assert s.post(P+'/check-ins',json=payload).status_code==200
    assert reserved(pid)==half
    payload.update(minutes=20,proportion=1)
    assert s.post(P+'/check-ins',json=payload).status_code==200
    assert reserved(pid)==before-item['minutes']
    payload['proportion']=.5
    assert s.post(P+'/check-ins',json=payload).status_code==422

@pytest.mark.parametrize('global_change',[False,True])
def test_replan_preserves_remaining_time(clients,global_change):
    gid,pid,item=setup_item(clients);s=clients['student']
    assert s.post(P+'/check-ins',json={'path_id':pid,'item_id':item['id'],'minutes':10,'proportion':.5}).status_code==200
    if global_change:
        b=s.get(P+'/learners/me/budget').json()
        assert s.patch(P+'/learners/me/budget',json={**b,'daily_minutes':b['daily_minutes']*2,'weekly_minutes':b['weekly_minutes']*2}).status_code==200
    candidate=planning(s,gid,True)
    task=next(t for t in s.get(P+'/paths/'+candidate).json()['tasks'] if t['skill_id']==item['skill_id'])
    import math
    assert task['minutes']==math.ceil(item['minutes']*.5)

@pytest.mark.parametrize('answer',['99',None])
def test_invalid_practice_answers_are_rejected(clients,answer):
    _,pid,item=setup_item(clients);s=clients['student']
    url=P+f'/paths/{pid}/items/{item["id"]}'
    qs=s.get(url+'/assessment').json()['questions']
    assert s.post(url+'/attempts',json={'answers':{q['id']:answer for q in qs},'minutes':1}).status_code==422

def test_changed_schedule_cannot_be_accepted(clients):
    gid,pid,item=setup_item(clients);s=clients['student'];candidate=planning(s,gid,True)
    with transaction() as db:
        p=one(db,'SELECT validation FROM paths WHERE id=:p',p=candidate)
        meta=json.loads(p['validation']);meta['schedule'][0]['date']='2000-01-01'
        run(db,'UPDATE paths SET validation=:v WHERE id=:p',v=json.dumps(meta),p=candidate)
    assert s.post(P+'/paths/'+candidate+'/accept').status_code==409
    assert s.get(P+'/paths/'+pid).json()['status']=='active'

def test_extra_question_rejected_without_evidence(clients):
    _,pid,item=setup_item(clients);s=clients['student']
    url=P+f'/paths/{pid}/items/{item["id"]}'
    qs=s.get(url+'/assessment').json()['questions']
    answers={q['id']:'0' for q in qs};answers['unknown']='0'
    assert s.post(url+'/attempts',json={'answers':answers,'minutes':1}).status_code==422
    assert s.get(url+'/assessment').json()['result'] is None
