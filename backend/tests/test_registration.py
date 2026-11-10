import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.mark.parametrize('role',['student','teacher'])
def test_self_registration(role):
    with TestClient(app) as c:
        body={'username':'new_'+role,'name':'新用户','role':role,'password':'MyPassword123!','confirm_password':'MyPassword123!'}
        route='/api/v1/auth/register'
        assert c.post(route,json={**body,'role':'admin'}).status_code==422
        assert c.post(route,json={**body,'confirm_password':'different'}).status_code==422
        assert c.post(route,json=body).status_code==201
        assert c.get('/api/v1/auth/me').status_code==401
        assert c.post(route,json=body).status_code==409
        user=c.post('/api/v1/auth/login',json={'username':body['username'],'password':body['password']}).json()
        assert user['role']==role and not user['must_change']
        assert c.get('/api/v1/admin/users').status_code==403
        if role=='student':assert c.get('/api/v1/learners/me/budget').status_code==200
