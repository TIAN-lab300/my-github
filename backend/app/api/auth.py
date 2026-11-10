import secrets
from datetime import datetime,timedelta,timezone
from fastapi import APIRouter,Depends,Request,Response
from app.core.db import transaction,one,rows,run,insert,uid,now,audit
from app.core.security import *
from app.schemas import Login,ChangePassword,Account

router=APIRouter()

class Registration(Account):
    confirm_password: str

@router.post('/auth/register',status_code=201)
def register(body:Registration):
    if not body.name.strip() or body.password!=body.confirm_password:
        fail(422,'请填写姓名，并确认两次密码一致')
    if body.username.lower()=='admin':
        fail(409,'该账号名不可用')
    encoded=password(body.password)
    with transaction() as db:
        if one(db,'SELECT id FROM users WHERE username=:n',n=body.username):
            fail(409,'该账号名已被使用')
        account_id=uid()
        insert(db,'users',id=account_id,username=body.username,name=body.name.strip(),role=body.role,
               password_hash=encoded,must_change=0,created_at=now())
        if body.role=='student':
            insert(db,'budgets',user_id=account_id)
        audit(db,account_id,'account_registered',account_id)
    return {'username':body.username}

@router.post('/auth/login')
def login(body:Login,request:Request,response:Response):
    username=body.username.strip()
    key=digest(username.lower()+':'+(request.client.host if request.client else 'local'))
    error=False
    with transaction() as db:
        attempt=one(db,'SELECT * FROM login_attempts WHERE key=:k',k=key)
        if attempt and attempt['until_at'] and attempt['until_at']>now():
            seconds=max(1,int((datetime.fromisoformat(attempt['until_at'])-datetime.now(timezone.utc)).total_seconds()))
            raise HTTPException(429,{'code':'LOGIN_COOLDOWN','message':f'尝试过于频繁，请{seconds}秒后重试','retry_after':seconds},headers={'Retry-After':str(seconds)})
        user=one(db,'SELECT * FROM users WHERE username=:n',n=username)
        if not verify(user['password_hash'] if user else DUMMY,body.password) or not user or user['status']!='active':
            n=(attempt['failures'] if attempt and (not attempt['until_at'] or attempt['until_at']>now()) else 0)+1
            until=(datetime.now(timezone.utc)+timedelta(minutes=15)).isoformat() if n>=5 else None
            run(db,'INSERT INTO login_attempts VALUES(:k,:n,:t) ON CONFLICT(key) DO UPDATE SET failures=:n,until_at=:t',k=key,n=n,t=until)
            audit(db,None,'login_failed',key,result='failed')
            error=True
        else:
            run(db,'DELETE FROM login_attempts WHERE key=:k',k=key)
            raw=secrets.token_urlsafe(32)
            old=request.cookies.get('zhixing_session','')
            run(db,'DELETE FROM sessions WHERE token_hash=:h',h=digest(old))
            insert(db,'sessions',token_hash=digest(raw),user_id=user['id'],auth_version=user['auth_version'],expires_at=(datetime.now(timezone.utc)+timedelta(hours=8)).isoformat())
            audit(db,user['id'],'login_succeeded',user['id'])
    if error:
        fail(401,'账号或密码不正确，或账号不可用','INVALID_CREDENTIALS')
    response.set_cookie('zhixing_session',raw,httponly=True,samesite='strict',secure=request.url.scheme=='https',max_age=28800)
    return public_user(user)

@router.get('/auth/me')
def me(user=Depends(current_user)):
    return public_user(user)

@router.post('/auth/logout')
def logout(request:Request,response:Response,user=Depends(current_user)):
    with transaction() as db:
        run(db,'DELETE FROM sessions WHERE token_hash=:t',t=digest(request.cookies.get('zhixing_session','')))
        audit(db,user['id'],'logout',user['id'])
    response.delete_cookie('zhixing_session')
    return {'ok':True}

@router.post('/auth/change-password')
def change(body:ChangePassword,response:Response,user=Depends(current_user)):
    if body.new_password!=body.confirm_password or body.new_password==body.old_password:
        fail(422,'新密码需一致且不能与旧密码相同')
    encoded=password(body.new_password)
    with transaction() as db:
        actual=one(db,'SELECT * FROM users WHERE id=:id',id=user['id'])
        if not verify(actual['password_hash'],body.old_password):
            fail(403,'旧密码不正确')
        run(db,'UPDATE users SET password_hash=:p,must_change=0,auth_version=auth_version+1 WHERE id=:id',p=encoded,id=user['id'])
        run(db,'DELETE FROM sessions WHERE user_id=:id',id=user['id'])
        audit(db,user['id'],'password_changed',user['id'])
    response.delete_cookie('zhixing_session')
    return {'ok':True}

@router.get('/admin/users')
def accounts(q:str='',page:int=1,account_role:str='',status:str='',user=Depends(current_user)):
    role(user,'admin')
    if account_role not in ('','admin','teacher','student') or status not in ('','active','disabled'): fail(422,'筛选条件无效')
    with transaction() as db:
        return rows(db,"SELECT id,username,name,role,status,must_change FROM users WHERE (username LIKE :q OR name LIKE :q) AND (:r='' OR role=:r) AND (:s='' OR status=:s) ORDER BY created_at,id LIMIT 50 OFFSET :o",q='%'+q[:100]+'%',r=account_role,s=status,o=max(0,page-1)*50)

@router.post('/admin/users',status_code=201)
def create(body:Account,user=Depends(current_user)):
    role(user,'admin')
    encoded=password(body.password)
    with transaction() as db:
        if one(db,'SELECT id FROM users WHERE username=:n',n=body.username):
            fail(409,'账号已存在')
        id=uid()
        insert(db,'users',id=id,username=body.username,name=body.name,role=body.role,password_hash=encoded,created_at=now())
        if body.role=='student': insert(db,'budgets',user_id=id)
        audit(db,user['id'],'account_created',id)
    return {'id':id}

@router.post('/admin/users/{id}/{action}')
def manage(id:str,action:str,user=Depends(current_user)):
    role(user,'admin')
    raw=None
    with transaction() as db:
        target=one(db,'SELECT * FROM users WHERE id=:id',id=id)
        if not target or target['role']=='admin': fail(403,'只能管理教师与学生账号')
        if action in ('disable','enable'):
            run(db,'UPDATE users SET status=:s,auth_version=auth_version+1 WHERE id=:id',s='active' if action=='enable' else 'disabled',id=id)
        elif action=='reset-password':
            raw=secrets.token_urlsafe(12)
            run(db,'UPDATE users SET password_hash=:p,must_change=1,auth_version=auth_version+1 WHERE id=:id',p=password(raw),id=id)
        else: fail(404,'操作不存在')
        run(db,'DELETE FROM sessions WHERE user_id=:id',id=id)
        audit(db,user['id'],action,id)
    return {'ok':True,'temporary_password':raw}

@router.patch('/users/me')
def edit_profile(body:dict,user=Depends(current_user)):
    name=str(body.get('name','')).strip()
    if not name or len(name)>80: fail(422,'请输入1至80字姓名')
    with transaction() as db: run(db,'UPDATE users SET name=:n WHERE id=:id',n=name,id=user['id'])
    return {'ok':True}

@router.get('/admin/audit')
def audits(page:int=1,action:str='',actor_id:str='',target_id:str='',start_at:str='',end_at:str='',result:str='',user=Depends(current_user)):
    role(user,'admin')
    if page<1: fail(422,'页码必须为正数')
    from datetime import datetime,timezone
    bounds={}
    for key,value in [('start',start_at),('end',end_at)]:
        if value:
            try:
                date=datetime.fromisoformat(value)
                if date.tzinfo is None: fail(422,'筛选时间必须包含时区')
                bounds[key]=date.astimezone(timezone.utc).isoformat()
            except ValueError: fail(422,'筛选时间格式错误')
    if bounds.get('start','')>bounds.get('end','9999'): fail(422,'开始时间晚于结束时间')
    if result and result not in ('success','failed'):fail(422,'审计结果筛选不合法')
    clauses=['action LIKE :action']
    params={'action':'%'+action[:80]+'%','offset':(page-1)*50}
    for column,value in [('actor_id',actor_id),('target_id',target_id),('result',result)]:
        if value:
            clauses.append(column+'=:'+column)
            params[column]=value
    for key,operator in [('start','>='),('end','<=')]:
        if key in bounds:
            clauses.append('created_at'+operator+':'+key)
            params[key]=bounds[key]
    with transaction() as db:
        return rows(db,'SELECT * FROM audit_logs WHERE '+' AND '.join(clauses)+' ORDER BY created_at DESC,id DESC LIMIT 50 OFFSET :offset',**params)
