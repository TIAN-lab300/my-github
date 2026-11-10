import secrets
from datetime import datetime,timedelta,timezone
from fastapi import APIRouter,Depends
from app.core.db import *
from app.core.security import *
from app.schemas import ClassInput,InviteInput

router=APIRouter()

@router.get('/classes')
def listing(user=Depends(current_user)):
    with transaction() as db:
        if user['role']=='teacher': return rows(db,'SELECT * FROM classes WHERE owner_id=:id',id=user['id'])
        if user['role']=='student': return rows(db,"SELECT c.* FROM classes c JOIN memberships m ON m.class_id=c.id WHERE m.user_id=:id AND m.status='active'",id=user['id'])
        return []

@router.post('/classes',status_code=201)
def create(body:ClassInput,user=Depends(current_user)):
    role(user,'teacher')
    with transaction() as db:
        id=uid(); insert(db,'classes',id=id,owner_id=user['id'],**body.model_dump())
        audit(db,user['id'],'class_created',id)
    return {'id':id}

@router.get('/classes/{id}')
def detail(id:str,user=Depends(current_user)):
    with transaction() as db:
        c=class_access(db,user,id)
        if user['role']=='student':
            c['membership']=one(db,'SELECT status FROM memberships WHERE class_id=:c AND user_id=:u',c=id,u=user['id'])
        c['members']=rows(db,"SELECT u.id,u.name,u.username,m.status FROM memberships m JOIN users u ON u.id=m.user_id WHERE m.class_id=:c",c=id) if user['role']=='teacher' else []
        return c

@router.patch('/classes/{id}')
def edit(id:str,body:dict,user=Depends(current_user)):
    with transaction() as db:
        c=class_access(db,user,id,True)
        if body.get('version')!=c['version']: fail(409,'班级版本已变化')
        status=body.get('status',c['status'])
        if status not in ('active','archived'): fail(422,'班级状态不合法')
        name=str(body.get('name',c['name'])).strip()
        if not name or len(name)>100: fail(422,'班级名称不合法')
        run(db,'UPDATE classes SET name=:n,description=:d,status=:s,version=version+1 WHERE id=:id',n=name,d=str(body.get('description',c['description']))[:1000],s=status,id=id)
        if status=='archived':
            run(db,"UPDATE invites SET status='revoked' WHERE class_id=:c",c=id)
            for a in rows(db,"SELECT a.id FROM assignments a JOIN tasks t ON t.id=a.task_id WHERE t.class_id=:c AND a.status NOT IN ('completed','cancelled')",c=id):
                run(db,"UPDATE assignments SET status='cancelled' WHERE id=:id",id=a['id'])
                run(db,"UPDATE reservations SET status='cancelled' WHERE source_type='teacher' AND source_id=:id AND status='active'",id=a['id'])
        for m in rows(db,"SELECT user_id FROM memberships WHERE class_id=:c AND status='active'",c=id): touch(db,m['user_id'])
        audit(db,user['id'],'class_updated',id)
    return {'ok':True}

@router.post('/classes/{id}/invites',status_code=201)
def invite(id:str,body:InviteInput,user=Depends(current_user)):
    with transaction() as db:
        class_access(db,user,id,True)
        raw=secrets.token_urlsafe(18); iid=uid()
        expires=(datetime.now(timezone.utc)+timedelta(hours=body.expires_in_hours)).isoformat()
        insert(db,'invites',id=iid,class_id=id,code_hash=digest(raw),expires_at=expires,max_uses=body.max_uses)
        audit(db,user['id'],'invite_created',iid)
    return {'id':iid,'code':raw,'expires_at':expires}

@router.get('/classes/{id}/invites')
def invites(id:str,user=Depends(current_user)):
    with transaction() as db:
        class_access(db,user,id,True)
        return rows(db,'SELECT id,expires_at,max_uses,used,status FROM invites WHERE class_id=:c',c=id)

@router.post('/classes/{id}/invites/{iid}/revoke')
def revoke(id:str,iid:str,user=Depends(current_user)):
    with transaction() as db:
        class_access(db,user,id,True)
        run(db,"UPDATE invites SET status='revoked' WHERE id=:i AND class_id=:c",i=iid,c=id)
        audit(db,user['id'],'invite_revoked',iid)
    return {'ok':True}

@router.post('/class-invites/{code}/join')
def join(code:str,user=Depends(current_user)):
    role(user,'student')
    with transaction() as db:
        i=one(db,'SELECT i.*,c.status AS class_status FROM invites i JOIN classes c ON c.id=i.class_id WHERE code_hash=:h',h=digest(code))
        if not i or i['status']!='active' or i['class_status']!='active' or i['expires_at']<now(): fail(410,'邀请码无效或过期')
        existing=one(db,"SELECT 1 FROM memberships WHERE class_id=:c AND user_id=:u AND status='active'",c=i['class_id'],u=user['id'])
        if existing: return {'class_id':i['class_id'],'already_joined':True}
        if i['used']>=i['max_uses']: fail(410,'邀请码次数已用尽')
        run(db,"INSERT INTO memberships(class_id,user_id) VALUES(:c,:u) ON CONFLICT(class_id,user_id) DO UPDATE SET status='active'",c=i['class_id'],u=user['id'])
        run(db,'UPDATE invites SET used=used+1 WHERE id=:id',id=i['id'])
        touch(db,user['id']); audit(db,user['id'],'class_joined',i['class_id'])
    return {'class_id':i['class_id']}

def remove_member(db,cid,student,actor):
    run(db,"UPDATE memberships SET status='left' WHERE class_id=:c AND user_id=:u",c=cid,u=student)
    assignments=rows(db,"SELECT a.id FROM assignments a JOIN tasks t ON t.id=a.task_id WHERE t.class_id=:c AND a.student_id=:u AND a.status!='completed'",c=cid,u=student)
    for a in assignments:
        run(db,"UPDATE assignments SET status='cancelled' WHERE id=:id",id=a['id'])
        run(db,"UPDATE reservations SET status='cancelled' WHERE source_type='teacher' AND source_id=:id",id=a['id'])
    touch(db,student); audit(db,actor,'member_removed',cid,student)

@router.post('/classes/{id}/leave')
def leave(id:str,user=Depends(current_user)):
    role(user,'student')
    with transaction() as db:
        class_access(db,user,id); remove_member(db,id,user['id'],user['id'])
    return {'ok':True}

@router.delete('/classes/{id}/members/{student}')
def remove(id:str,student:str,user=Depends(current_user)):
    with transaction() as db:
        class_access(db,user,id,True); remove_member(db,id,student,user['id'])
    return {'ok':True}
