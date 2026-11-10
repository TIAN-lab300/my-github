from fastapi.testclient import TestClient
from app.main import app
from app.core.db import transaction,one,run

def test_phone_not_configured(clients,monkeypatch):
    monkeypatch.delenv('SMS_GATEWAY_URL',raising=False)
    r=clients['student'].post('/api/v1/auth/phone/send',json={'phone':'13800138000'})
    assert r.status_code==503
    assert r.json()['code']=='SMS_NOT_CONFIGURED'

def test_bind_reset_and_replay(clients,monkeypatch):
    from app.api import phone
    codes=[]
    monkeypatch.setattr(phone,'send_sms',lambda p,c:codes.append(c))
    client=clients['student'];number='13800138000'
    assert client.post('/api/v1/auth/phone/send',json={'phone':number}).status_code==200
    assert client.post('/api/v1/auth/phone/send',json={'phone':number}).status_code==429
    assert client.post('/api/v1/auth/phone/bind',json={'phone':number,'code':codes[-1]}).status_code==200
    assert client.get('/api/v1/auth/phone').json()['phone']=='138****8000'
    assert clients['student2'].post('/api/v1/auth/phone/send',json={'phone':number}).status_code==409
    with transaction() as db:run(db,"UPDATE sms_codes SET created_at='2000-01-01T00:00:00+00:00'")
    guest=TestClient(app)
    assert guest.post('/api/v1/auth/phone/reset/send',json={'username':'student','phone':number}).status_code==200
    body={'username':'student','phone':number,'code':codes[-1],'new_password':'NewPassword123!','confirm_password':'NewPassword123!'}
    assert guest.post('/api/v1/auth/phone/reset',json=body).status_code==200
    assert client.get('/api/v1/auth/me').status_code==401
    assert guest.post('/api/v1/auth/phone/reset',json=body).status_code==422
    assert guest.post('/api/v1/auth/login',json={'username':'student','password':'NewPassword123!'}).status_code==200

def test_code_attempts_commit(clients,monkeypatch):
    from app.api import phone
    codes=[];monkeypatch.setattr(phone,'send_sms',lambda p,c:codes.append(c))
    client=clients['student'];number='13900139000'
    assert client.post('/api/v1/auth/phone/send',json={'phone':number}).status_code==200
    wrong='000000' if codes[0]!='000000' else '111111'
    for _ in range(5):assert client.post('/api/v1/auth/phone/bind',json={'phone':number,'code':wrong}).status_code==422
    assert client.post('/api/v1/auth/phone/bind',json={'phone':number,'code':codes[0]}).status_code==422

def test_expired_and_unauthorized(clients,monkeypatch):
    from app.api import phone
    codes=[];monkeypatch.setattr(phone,'send_sms',lambda p,c:codes.append(c))
    assert TestClient(app).post('/api/v1/auth/phone/send',json={'phone':'13800138000'}).status_code==401
    c=clients['student'];c.post('/api/v1/auth/phone/send',json={'phone':'13800138000'})
    with transaction() as db:run(db,"UPDATE sms_codes SET expires_at='2000-01-01T00:00:00+00:00'")
    assert c.post('/api/v1/auth/phone/bind',json={'phone':'13800138000','code':codes[0]}).status_code==422
