"""One independently named acceptance case per selected subfunction."""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.db import transaction,run,rows
P='/api/v1'
IDS=['SF-AUTH-01','SF-AUTH-02','SF-AUTH-05','SF-AUTH-06','SF-AUTH-08','SF-AUTH-09','SF-AUTH-10','SF-AUTH-11','SF-AUTH-12','SF-AUTH-14','SF-ACCOUNT-02','SF-ACCOUNT-03','SF-ACCOUNT-05','SF-ACCOUNT-06','SF-ACCOUNT-07']
@pytest.mark.parametrize('sf',IDS,ids=IDS)
def test_subfunction(sf,clients):
    admin=clients['admin'];s=clients['student'];c=TestClient(app)
    def login(name='student',pw='TestPassword123!'):
        return c.post(P+'/auth/login',json={'username':name,'password':pw})
    if sf=='SF-AUTH-01':
        for name in ('admin','teacher','student'):
            assert login(name).status_code==200
            assert c.get(P+'/auth/me').json()['role']==name
        assert login('unknown').status_code==401
    elif sf=='SF-AUTH-02':
        assert c.post(P+'/auth/login',json={'username':'','password':''}).status_code==422
        assert login(' student ').status_code==200
        assert login('student',' TestPassword123!').status_code==401
    elif sf=='SF-AUTH-05':
        with transaction() as db: run(db,"UPDATE users SET must_change=1 WHERE id='student'")
        assert login().json()['must_change']==1
        assert c.get(P+'/resources').status_code==403
        assert c.post(P+'/auth/change-password',json={'old_password':'TestPassword123!','new_password':'ChangedPassword!12','confirm_password':'ChangedPassword!12'}).status_code==200
        assert login(pw='ChangedPassword!12').json()['must_change']==0
    elif sf=='SF-AUTH-06':
        assert login().status_code==200
        assert c.post(P+'/auth/change-password',json={'old_password':'wrong','new_password':'ChangedPassword!12','confirm_password':'ChangedPassword!12'}).status_code==403
        assert c.post(P+'/auth/change-password',json={'old_password':'TestPassword123!','new_password':'ChangedPassword!12','confirm_password':'ChangedPassword!12'}).status_code==200
        assert s.get(P+'/auth/me').status_code==401
    elif sf=='SF-AUTH-08':
        assert s.get(P+'/auth/me').json()['role']=='student'
        assert s.get(P+'/admin/users').status_code==403
        assert s.post(P+'/classes',json={'name':'越权班级'}).status_code==403
    elif sf=='SF-AUTH-09':
        with transaction() as db: run(db,"UPDATE sessions SET expires_at='2000-01-01T00:00:00+00:00' WHERE user_id='student'")
        assert s.get(P+'/auth/me').status_code==401
        assert s.get(P+'/resources').status_code==401
    elif sf=='SF-AUTH-10':
        assert s.post(P+'/auth/logout').status_code==200
        assert s.get(P+'/auth/me').status_code==401
    elif sf=='SF-AUTH-11':
        admin.post(P+'/admin/users/student/disable');assert s.get(P+'/auth/me').status_code==401
        admin.post(P+'/admin/users/teacher/reset-password');assert clients['teacher'].get(P+'/auth/me').status_code==401
    elif sf=='SF-AUTH-12':
        for _ in range(5): assert login(pw='wrong').status_code==401
        limited=login();assert limited.status_code==429 and int(limited.headers['retry-after'])>0
        with transaction() as db: run(db,"UPDATE login_attempts SET until_at='2000-01-01T00:00:00+00:00'")
        assert login().status_code==200
    elif sf=='SF-AUTH-14':
        login();login(pw='wrong');c.post(P+'/auth/logout')
        events=admin.get(P+'/admin/audit').json();actions={e['action'] for e in events}
        assert {'login_succeeded','login_failed','logout'}<=actions
        assert 'TestPassword123!' not in str(events)
    elif sf=='SF-ACCOUNT-02':
        body={'username':'created','name':'新账号','role':'student','password':'TemporaryPassword!12'}
        assert admin.post(P+'/admin/users',json=body).status_code==201
        assert admin.post(P+'/admin/users',json=body).status_code==409
        assert login('created',body['password']).json()['must_change']==1
    elif sf=='SF-ACCOUNT-03':
        filtered=admin.get(P+'/admin/users',params={'account_role':'teacher','status':'active','q':'teacher'}).json()
        assert len(filtered)==2 and all(u['role']=='teacher' and 'password_hash' not in u for u in filtered)
        assert admin.get(P+'/admin/users',params={'page':2}).json()==[]
        assert admin.get(P+'/admin/users',params={'status':'invalid'}).status_code==422
    elif sf=='SF-ACCOUNT-05':
        admin.post(P+'/admin/users/student/disable');assert login().status_code==401
        admin.post(P+'/admin/users/student/enable');assert s.get(P+'/auth/me').status_code==401
        assert login().status_code==200
    elif sf=='SF-ACCOUNT-06':
        reset=admin.post(P+'/admin/users/student/reset-password').json()
        assert reset['temporary_password'] and s.get(P+'/auth/me').status_code==401
        assert login(pw=reset['temporary_password']).json()['must_change']==1
    elif sf=='SF-ACCOUNT-07':
        assert s.patch(P+'/users/me',json={'name':'学生','role':'admin'}).status_code==200
        assert s.get(P+'/auth/me').json()['role']=='student'
        assert admin.post(P+'/admin/users/admin/disable').status_code==403
        assert admin.post(P+'/admin/users',json={'username':'badadmin','name':'不允许','role':'admin','password':'TemporaryPassword!12'}).status_code==422
    c.close()
