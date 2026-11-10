from datetime import datetime, timedelta, timezone

from app.core.db import transaction, run
from test_platform import P, classroom


def test_sf_class_02_and_06(clients):
    cid, _ = classroom(clients)
    url = P + '/classes'
    for actor, visible in [('teacher', True), ('teacher2', False), ('student', True), ('student2', False)]:
        response = clients[actor].get(url)
        assert response.status_code == 200
        assert (cid in [row['id'] for row in response.json()]) == visible
    teacher_view = clients['teacher'].get(f'{url}/{cid}').json()
    assert [(m['id'], m['status']) for m in teacher_view['members']] == [('student', 'active')]
    assert clients['student'].get(f'{url}/{cid}').json()['members'] == []
    assert clients['student'].get(f'{url}/{cid}').json()['membership'] == {'status':'active'}
    private = f'{P}/teacher/classes/{cid}/students/student/profile'
    assert clients['student2'].get(private).status_code in (403,404)
    assert clients['teacher2'].get(f'{url}/{cid}').status_code == 403
    assert clients['student2'].get(f'{url}/{cid}').status_code == 404


def test_sf_class_01(clients):
    cid, _ = classroom(clients)
    url = P + '/classes/' + cid
    teacher = clients['teacher']
    original = teacher.get(url).json()
    edit = {'version': original['version'], 'name': 'updated', 'description': 'new description'}
    assert clients['teacher2'].patch(url, json=edit).status_code == 403
    assert teacher.patch(url, json=edit).status_code == 200
    assert teacher.patch(url, json={**edit, 'name':'stale'}).status_code == 409
    current = teacher.get(url).json()
    assert (current['name'], current['description']) == ('updated', 'new description')
    assert teacher.patch(url,json={'version':current['version'],'status':'archived'}).status_code == 200
    assert teacher.patch(url,json={**edit,'version':current['version']+1}).status_code == 409


def test_sf_class_04(clients):
    cid, _ = classroom(clients)
    teacher, outsider = clients['teacher'], clients['student2']
    invites = P + f'/classes/{cid}/invites'
    def issue():
        response = teacher.post(invites, json={'max_uses':1})
        assert response.status_code == 201
        return response.json()
    def denied(code):
        response = outsider.post(P + '/class-invites/' + code + '/join')
        assert response.status_code == 410 and response.json()['message']
    denied('unknown')
    invite = issue()
    with transaction() as db:
        run(db,'UPDATE invites SET expires_at=:t WHERE id=:id',t=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat(),id=invite['id'])
    denied(invite['code'])
    invite = issue()
    assert teacher.post(invites+'/'+invite['id']+'/revoke').status_code == 200
    denied(invite['code'])
    invite = issue()
    with transaction() as db:
        run(db,'UPDATE invites SET used=max_uses WHERE id=:id',id=invite['id'])
    denied(invite['code'])
    invite = issue()
    url = P + '/classes/' + cid
    assert teacher.patch(url,json={'version':teacher.get(url).json()['version'],'status':'archived'}).status_code == 200
    denied(invite['code'])
    assert outsider.get(P + '/classes').json() == []

def test_sf_ops_03(clients, monkeypatch, tmp_path):
    from app.core import db
    admin = clients['admin']
    health = '/api/v1/health'
    checks=admin.get(health).json()['checks']
    assert {key:checks[key] for key in ('database','files','model')} == {
        'database':'ok', 'files':'ok', 'model':'not_configured'}
    assert all(key in checks for key in ('ocr','asr','embedding','search'))
    config = admin.post(P+'/admin/model-configs',json={'model':'qwen-plus','secret_env':'TEST_HEALTH_SECRET'}).json()
    with transaction() as connection:
        run(connection,"UPDATE model_configs SET status='active' WHERE id=:id",id=config['id'])
    monkeypatch.delenv('TEST_HEALTH_SECRET',raising=False)
    assert admin.get(health).json()['checks']['model']=='missing_key'
    monkeypatch.setenv('TEST_HEALTH_SECRET','private-test-value')
    response=admin.get(health)
    assert response.json()['checks']['model']=='configured'
    assert 'private-test-value' not in response.text and 'TEST_HEALTH_SECRET' not in response.text
    monkeypatch.setattr(db,'DATA',tmp_path/'absent')
    response=admin.get(health)
    assert response.status_code==503 and response.json()['checks']['files']=='unavailable'

def test_resource_filters_preserve_authorization(clients):
    from test_platform import resource
    cid,_=classroom(clients)
    rid=resource(clients,cid)
    url=P+'/resources'
    params={'class_id':cid,'kind':'text','tag':'Python','status':'published','parse_status':'ready'}
    assert [r['id'] for r in clients['student'].get(url,params=params).json()]==[rid]
    assert clients['student2'].get(url,params=params).json()==[]
    assert clients['student'].get(url,params={**params,'status':'draft'}).json()==[]
    assert clients['student'].get(url,params={'page':0}).status_code==422
    assert clients['student'].get(url,params={'parse_status':'invalid'}).status_code==422


def test_audit_filters_and_access(clients):
    cid,_=classroom(clients)
    url=P+'/admin/audit'
    admin=clients['admin']
    params={'actor_id':'teacher','target_id':cid,'action':'class_created'}
    response=admin.get(url,params=params)
    assert response.status_code==200
    assert len(response.json())==1
    assert response.json()[0]['target_id']==cid
    assert admin.get(url,params={**params,'actor_id':'student'}).json()==[]
    assert admin.get(url,params={'start_at':'2999-01-01T00:00:00+00:00'}).json()==[]
    assert admin.get(url,params={'start_at':'bad'}).status_code==422
    assert admin.get(url,params={'start_at':'2026-01-01'}).status_code==422
    assert clients['student'].get(url).status_code==403
    assert clients['student'].delete(url).status_code==405
