import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from fastapi import Depends, HTTPException, Request

from .db import transaction, one, run, insert, audit, now

hasher = PasswordHasher()
DUMMY = hasher.hash(secrets.token_urlsafe(24))

def fail(status, message, code='INVALID_REQUEST'):
    raise HTTPException(status, {'code': code, 'message': message})

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def password(value):
    if len(value) < 10 or len(value) > 128:
        fail(422, '密码长度应为10至128位')
    return hasher.hash(value)

def verify(encoded, value):
    try:
        return hasher.verify(encoded, value)
    except (VerifyMismatchError, InvalidHashError):
        return False

def public_user(user):
    return {k: user[k] for k in ('id','username','name','role','status','must_change')}

def current_user(request: Request):
    token = request.cookies.get('zhixing_session', '')
    with transaction() as db:
        user = one(db, '''SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id
          WHERE s.token_hash=:token AND s.expires_at>:time AND s.auth_version=u.auth_version AND u.status='active' ''', token=digest(token), time=now())
    if not user:
        fail(401, '请登录或重新登录', 'UNAUTHENTICATED')
    if user['must_change'] and request.url.path not in ('/api/v1/auth/me','/api/v1/auth/change-password','/api/v1/auth/logout'):
        fail(403, '首次登录请先修改密码', 'PASSWORD_CHANGE_REQUIRED')
    request.state.actor_id=user['id']
    return user

def role(user, *roles):
    if user['role'] not in roles:
        fail(403, '当前身份无权执行该操作', 'FORBIDDEN')

def class_access(db, user, class_id, write=False):
    c = one(db, 'SELECT * FROM classes WHERE id=:id', id=class_id)
    if not c:
        fail(404, '班级不存在')
    owner = user['role']=='teacher' and c['owner_id']==user['id']
    member = one(db, "SELECT 1 FROM memberships WHERE class_id=:c AND user_id=:u AND status='active'", c=class_id,u=user['id'])
    if not owner and (write or user['role']!='student' or not member):
        fail(404 if user['role']=='student' else 403, '无权访问该班级')
    if write and c['status']!='active':
        fail(409, '班级已归档，只能查询历史')
    return c

def resource_access(db, user, resource_id, write=False):
    r=one(db, 'SELECT * FROM resources WHERE id=:id', id=resource_id)
    if not r:
        fail(404, '资料不存在')
    if write:
        if r['owner_id']!=user['id']:
            fail(403,'只能管理本人资料')
        if r['class_id']:
            class_access(db,user,r['class_id'],True)
    elif r['owner_id']!=user['id']:
        if r['status']!='published':
            fail(404,'资料不可访问')
        if r['scope']=='class':
            class_access(db,user,r['class_id'])
        elif r['scope']!='school':
            fail(404,'资料不可访问')
    return r

def goal_access(db, user, goal_id):
    role(user,'student')
    g=one(db,'SELECT * FROM goals WHERE id=:id AND student_id=:u',id=goal_id,u=user['id'])
    if not g:
        fail(404,'目标不存在')
    return g
