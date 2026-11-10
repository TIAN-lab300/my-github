"""Phone ownership verification through an operator-configured HTTPS SMS gateway."""
import os,secrets
from datetime import datetime,timedelta,timezone
import httpx
from fastapi import APIRouter,Depends,Response
from pydantic import BaseModel,Field
from app.core.db import transaction,one,run,insert,uid,now,audit
from app.core.security import current_user,fail,password,digest
router=APIRouter()
class Phone(BaseModel):
    phone:str=Field(pattern=r'^1[3-9][0-9]{9}$')
class Verify(Phone):
    code:str=Field(pattern=r'^[0-9]{6}$')
class Reset(Verify):
    username:str=Field(min_length=2,max_length=80)
    new_password:str=Field(min_length=10,max_length=128)
    confirm_password:str
class ResetSend(Phone):
    username:str=Field(min_length=2,max_length=80)

def send_sms(phone,code):
    url=os.getenv('SMS_GATEWAY_URL','');token=os.getenv('SMS_GATEWAY_TOKEN','')
    if not url.startswith('https://') or not token:fail(503,'短信服务尚未配置，请配置短信网关后再发送','SMS_NOT_CONFIGURED')
    try:
        r=httpx.post(url,json={'phone':phone,'code':code,'expires_in':300},headers={'Authorization':'Bearer '+token},timeout=10,follow_redirects=False)
        if r.status_code!=200 or r.json().get('accepted') is not True:raise ValueError()
    except Exception:fail(502,'短信服务暂不可用，请稍后重试','SMS_DELIVERY_FAILED')

def issue(user_id,phone,purpose):
    code=f'{secrets.randbelow(1000000):06d}';at=datetime.now(timezone.utc)
    with transaction() as db:
        recent=one(db,"SELECT COUNT(*) AS n,MAX(created_at) AS latest FROM sms_codes WHERE (phone=:p OR user_id=:u) AND created_at>:t",p=phone,u=user_id,t=(at-timedelta(hours=1)).isoformat())
        if recent['n']>=5 or (recent['latest'] and recent['latest']>(at-timedelta(seconds=60)).isoformat()):fail(429,'请稍后重试，每60秒一次，每小时最多5次')
        # Serialize delivery and reservation to prevent concurrent sends bypassing limits.
        send_sms(phone,code)
        run(db,'UPDATE sms_codes SET used=1 WHERE user_id=:u AND purpose=:p',u=user_id,p=purpose)
        ident=uid()
        insert(db,'sms_codes',id=ident,user_id=user_id,phone=phone,purpose=purpose,code_hash=password(code+'-sms-verification'),created_at=at.isoformat(),expires_at=(at+timedelta(minutes=5)).isoformat())
        audit(db,user_id,'sms_requested',ident)
    return {'ok':True,'retry_after':60,'expires_in':300}

def consume(db,user_id,phone,purpose,code):
    from app.core.security import verify
    row=one(db,'SELECT * FROM sms_codes WHERE user_id=:u AND phone=:p AND purpose=:s AND used=0 ORDER BY created_at DESC LIMIT 1',u=user_id,p=phone,s=purpose)
    if not row or row['expires_at']<=now() or row['attempts']>=5:return False
    run(db,'UPDATE sms_codes SET attempts=attempts+1 WHERE id=:i',i=row['id'])
    if not verify(row['code_hash'],code+'-sms-verification'):return False
    run(db,'UPDATE sms_codes SET used=1 WHERE id=:i',i=row['id'])
    return True

@router.get('/auth/phone')
def status(user=Depends(current_user)):
    with transaction() as db:r=one(db,'SELECT phone FROM user_phones WHERE user_id=:u',u=user['id'])
    return {'phone':r['phone'][:3]+'****'+r['phone'][-4:] if r else None}

@router.post('/auth/phone/send')
def send(body:Phone,user=Depends(current_user)):
    with transaction() as db:
        if one(db,'SELECT 1 FROM user_phones WHERE phone=:p OR user_id=:u',p=body.phone,u=user['id']):fail(409,'该账号或手机号已绑定，请联系管理员处理换绑')
    return issue(user['id'],body.phone,'bind')

@router.post('/auth/phone/bind')
def bind(body:Verify,user=Depends(current_user)):
    with transaction() as db:
        if one(db,'SELECT 1 FROM user_phones WHERE phone=:p OR user_id=:u',p=body.phone,u=user['id']):fail(409,'该账号或手机号已绑定')
        ok=consume(db,user['id'],body.phone,'bind',body.code)
        if ok:
            insert(db,'user_phones',user_id=user['id'],phone=body.phone,verified_at=now())
            audit(db,user['id'],'phone_bound',user['id'])
    if not ok:fail(422,'验证码错误、过期或尝试次数已用完')
    return {'ok':True}

@router.post('/auth/phone/reset/send')
def reset_send(body:ResetSend):
    with transaction() as db:r=one(db,"SELECT u.id FROM users u JOIN user_phones p ON u.id=p.user_id WHERE u.username=:n AND p.phone=:p AND u.status='active'",n=body.username,p=body.phone)
    if not r:fail(422,'账号或绑定手机号不匹配')
    return issue(r['id'],body.phone,'reset')

@router.post('/auth/phone/reset')
def reset(body:Reset,response:Response):
    if body.new_password!=body.confirm_password:fail(422,'两次新密码不一致')
    encoded=password(body.new_password)
    with transaction() as db:
        r=one(db,"SELECT u.id FROM users u JOIN user_phones p ON u.id=p.user_id WHERE u.username=:n AND p.phone=:p AND u.status='active'",n=body.username,p=body.phone)
        ok=bool(r) and consume(db,r['id'],body.phone,'reset',body.code)
        if ok:
            run(db,'UPDATE users SET password_hash=:p,must_change=0,auth_version=auth_version+1 WHERE id=:u',p=encoded,u=r['id'])
            run(db,'DELETE FROM sessions WHERE user_id=:u',u=r['id'])
            audit(db,r['id'],'password_reset_by_phone',r['id'])
    if not ok:fail(422,'账号、手机号或验证码无效')
    response.delete_cookie('zhixing_session')
    return {'ok':True}
