import json,hashlib
import logging
from fastapi import APIRouter,Depends
from app.core.db import *
from app.core.security import *
from app.services.learning import actual_events,mastery

router=APIRouter()

def protect_class_goals(db,payload,class_id):
    """Apply current goal-sharing permissions to historical presentation."""
    shared={g['id'] for g in rows(db,'SELECT id FROM goals WHERE class_id=:c',c=class_id)}
    for student in payload.get('students',[]):
        context=student.get('learning_context',{})
        context['goals']=[g for g in context.get('goals',[]) if g['id'] in shared]
    return payload

def calculate(db,student,class_id=None):
    args={'u':student};where=''
    if class_id: where=' AND t.class_id=:c';args['c']=class_id
    assignments=rows(db,"SELECT a.*,t.due_at FROM assignments a JOIN tasks t ON t.id=a.task_id WHERE a.student_id=:u AND t.status IN ('published','closed') AND a.status!='cancelled'"+where,**args)
    done=[a for a in assignments if a['status']=='completed']
    overdue=[a for a in assignments if a['status']!='completed' and a['due_at']<now()]
    ontime=[a for a in done if a['first_completed_at'] and a['first_completed_at']<=a['due_at']]
    events=actual_events(db,student,class_id);m=mastery(db,student,class_id)
    pending=one(db,"SELECT count(*) AS n FROM attempts WHERE student_id=:u AND status='pending_review'"+(' AND class_id=:c' if class_id else ''),**args)['n']
    goals=rows(db,"SELECT id,title,status FROM goals WHERE student_id=:u AND status!='archived'"+(' AND class_id=:c' if class_id else ''),**args)
    risks=[]
    if overdue: risks.append({'reason':'任务逾期未交','count':len(overdue),'evidence_ids':[a['id'] for a in overdue],'observed_at':max(a['due_at'] for a in overdue)})
    weak=[s for s,v in m.items() if v['probability']<.45]
    if weak:
        latest=one(db,"SELECT max(a.created_at) AS time FROM attempts a WHERE a.student_id=:u"+(' AND a.class_id=:c' if class_id else ''),**args)
        risks.append({'reason':'有效测验证据低于0.45','skills':weak,'evidence_ids':[m[s]['last_update']['evidence_id'] for s in weak],'observed_at':latest['time']})
    reading=one(db,"SELECT count(*) AS total,coalesce(sum(completed),0) AS completed FROM study_sessions WHERE student_id=:u"+(' AND class_id=:c' if class_id else ''),**args)
    layers={'reading':{'completed':reading['completed'],'total':reading['total']},
            'submission':{'completed':len(done),'assigned':len(assignments)},
            'mastery':{'mastered':sum(v['probability']>=.75 for v in m.values()),'tested':len(m)}}
    return {'query_window':{'kind':'all_time','from':min((e['created_at'] for e in events),default=None),'through':max((e['created_at'] for e in events),default=None)},'progress_layers':layers,'learning_context':{'goals':goals,'class_id':class_id},'learning_behavior':{'actual_minutes':sum(e['minutes'] for e in events),'completed':len(done),'assigned':len(assignments),'completion_rate':len(done)/len(assignments) if assignments else None,'on_time_rate':len(ontime)/len(done) if done else None,'overdue':len(overdue)},'mastery_state':m,'evidence_quality':{'pending_review':pending,'valid_observations':sum(x['evidence_count'] for x in m.values())},'risk_summary':risks,'data_quality':{'status':'current','rules_version':'profile-v1','unknown_is_weak':False}}

def snapshot(db,scope,scope_id,payload,watermark):
    old=one(db,'SELECT * FROM profile_snapshots WHERE scope=:s AND scope_id=:id AND watermark=:w',s=scope,id=scope_id,w=watermark)
    if old: return {**json.loads(old['payload']),'snapshot_id':old['id'],'version':old['version'],'generated_at':old['created_at']}
    v=one(db,'SELECT count(*) AS n FROM profile_snapshots WHERE scope=:s AND scope_id=:id',s=scope,id=scope_id)['n']+1
    id=uid();time=now();insert(db,'profile_snapshots',id=id,scope=scope,scope_id=scope_id,watermark=watermark,payload=dump(payload),version=v,created_at=time)
    return {**payload,'snapshot_id':id,'version':v,'generated_at':time}

@router.get('/learners/me/profile')
@router.get('/learners/me/progress')
def mine(user=Depends(current_user)):
    role(user,'student')
    try:
        with transaction() as db:
            w=one(db,'SELECT watermark FROM users WHERE id=:id',id=user['id'])['watermark']
            payload=calculate(db,user['id'])
            watermark=hashlib.sha256(dump({'source':w,'payload':payload}).encode()).hexdigest()
            result=snapshot(db,'student',user['id'],payload,watermark)
            run(db,"UPDATE profile_refresh_events SET status='processed',snapshot_id=:s,error=NULL,processed_at=:t WHERE student_id=:u AND source_watermark<=:w AND status!='processed'",s=result['snapshot_id'],t=now(),u=user['id'],w=w)
            return result
    except Exception:
        logging.getLogger(__name__).exception('Profile refresh failed for user %s',user['id'])
        with transaction() as db:
            run(db,"UPDATE profile_refresh_events SET status='failed',error='画像刷新失败，可重试',processed_at=:t WHERE student_id=:u AND status='pending'",u=user['id'],t=now())
            old=one(db,"SELECT * FROM profile_snapshots WHERE scope='student' AND scope_id=:u ORDER BY version DESC LIMIT 1",u=user['id'])
        if not old: fail(503,'画像刷新失败，暂无有效历史快照，请稍后重试','PROFILE_UNAVAILABLE')
        payload=json.loads(old['payload'])
        payload['data_quality']={**payload.get('data_quality',{}),'status':'stale','refresh_error':'刷新失败，当前显示上一有效版本'}
        return {**payload,'snapshot_id':old['id'],'version':old['version'],'generated_at':old['created_at']}

@router.get('/learners/me/profile/refresh-events')
def refresh_events(user=Depends(current_user)):
    role(user,'student')
    with transaction() as db:
        return rows(db,'SELECT id,source_watermark,status,snapshot_id,error,created_at,processed_at FROM profile_refresh_events WHERE student_id=:u ORDER BY source_watermark DESC LIMIT 50',u=user['id'])

@router.post('/learners/me/profile/refresh')
def retry_refresh(user=Depends(current_user)):
    return mine(user)

@router.get('/learners/me/profile/history')
def history(user=Depends(current_user)):
    role(user,'student')
    with transaction() as db:
        return rows(db,"SELECT id,version,created_at,payload FROM profile_snapshots WHERE scope='student' AND scope_id=:u ORDER BY version DESC LIMIT 50",u=user['id'])

@router.get('/learning-records')
def records(start:str='',end:str='',class_id:str='',goal_id:str='',resource_id:str='',task_id:str='',source:str='',page:int=1,user=Depends(current_user)):
    from datetime import date,timedelta
    role(user,'student')
    if page<1: fail(422,'页码必须为正数')
    if source not in ('','reading','assessment','checkin'): fail(422,'记录类型无效')
    try:
        lo=date.fromisoformat(start).isoformat() if start else ''
        hi=(date.fromisoformat(end)+timedelta(days=1)).isoformat() if end else ''
    except ValueError: fail(422,'日期格式无效')
    if lo and hi and lo>=hi: fail(422,'开始日期不能晚于结束日期')
    params={'u':user['id'],'offset':max(page-1,0)*50}
    conditions=[]
    if lo: conditions.append('x.created_at>=:lo');params['lo']=lo
    if hi: conditions.append('x.created_at<:hi');params['hi']=hi
    if class_id: conditions.append('x.class_id=:class_id');params['class_id']=class_id
    if goal_id: conditions.append('x.goal_id=:goal_id');params['goal_id']=goal_id
    if resource_id: conditions.append('x.resource_id=:resource_id');params['resource_id']=resource_id
    if task_id: conditions.append('x.task_id=:task_id');params['task_id']=task_id
    suffix=''.join(' AND '+c for c in conditions)
    queries={
      'study_sessions':("SELECT s.*,r.title,NULL AS goal_id,NULL AS task_id FROM study_sessions s JOIN resources r ON r.id=s.resource_id",'reading'),
      'attempts':('SELECT at.*,a.task_id,NULL AS resource_id FROM attempts at LEFT JOIN assignments a ON a.id=at.assignment_id','assessment'),
      'checkins':('SELECT c.*,p.goal_id,g.class_id,NULL AS resource_id,NULL AS task_id FROM checkins c JOIN paths p ON p.id=c.path_id JOIN goals g ON g.id=p.goal_id','checkin')}
    result={}
    with transaction() as db:
        for key,(query,kind) in queries.items():
            result[key]=rows(db,'SELECT * FROM ('+query+') x WHERE x.student_id=:u'+suffix+' ORDER BY x.created_at DESC LIMIT 50 OFFSET :offset',**params) if not source or source==kind else []
    return {**result,'page':max(page,1),'page_size':50,'timezone':'UTC','message':'日期范围按记录UTC日期筛选，每类独立分页'}

def current_classroom(id:str,user):
    role(user,'teacher')
    with transaction() as db:
        c=class_access(db,user,id)
        students=rows(db,"SELECT u.id,u.name,u.watermark FROM users u JOIN memberships m ON m.user_id=u.id WHERE m.class_id=:c AND m.status='active'",c=id)
        projections=[{'student_id':s['id'],'name':s['name'],**calculate(db,s['id'],id)} for s in students]
        assigned=sum(p['learning_behavior']['assigned'] for p in projections);done=sum(p['learning_behavior']['completed'] for p in projections)
        payload={'class_scope':c,'students':projections,'task_metrics':{'assigned':assigned,'completed':done,'completion_rate':done/assigned if assigned else None},'learning_time':sum(p['learning_behavior']['actual_minutes'] for p in projections),'risk_students':sum(bool(p['risk_summary']) for p in projections),'data_quality':{'status':'current','evidence_students':sum(bool(p['mastery_state']) for p in projections)}}
        # Include time buckets because overdue status changes even without a write event.
        distribution={}
        for student in projections:
            for skill,value in student['mastery_state'].items():
                item=distribution.setdefault(skill,{'tested':0,'mastered':0,'weak':0})
                item['tested']+=1
                item['mastered']+=int(value['probability']>=.75)
                item['weak']+=int(value['probability']<.45)
        payload['mastery_distribution']=distribution
        payload['query_window']='all_time'
        w=hashlib.sha256(dump({'students':students,'class_version':c['version'],'hour':now()[:13],'payload':payload}).encode()).hexdigest()
        return snapshot(db,'class',id,payload,w)

@router.get('/teacher/classes/{id}/profile')
def classroom(id:str,user=Depends(current_user)):
    role(user,'teacher')
    with transaction() as db: class_access(db,user,id)
    try:
        return current_classroom(id,user)
    except Exception:
        logging.getLogger(__name__).exception('Class profile refresh failed')
        with transaction() as db:
            old=one(db,"SELECT * FROM profile_snapshots WHERE scope='class' AND scope_id=:id ORDER BY version DESC LIMIT 1",id=id)
        if not old: fail(503,'班级画像暂无有效快照，请稍后重试','CLASS_PROFILE_UNAVAILABLE')
        with transaction() as db:
            payload=protect_class_goals(db,json.loads(old['payload']),id)
        payload['data_quality']={**payload.get('data_quality',{}),'status':'stale','refresh_error':'刷新失败，显示上一有效版本'}
        return {**payload,'snapshot_id':old['id'],'version':old['version'],'generated_at':old['created_at']}

@router.get('/teacher/classes/{id}/profile/history')
def class_history(id:str,user=Depends(current_user)):
    role(user,'teacher')
    with transaction() as db:
        class_access(db,user,id)
        history=rows(db,"SELECT id,version,payload,created_at FROM profile_snapshots WHERE scope='class' AND scope_id=:id ORDER BY version DESC LIMIT 50",id=id)
        for item in history:
            item['payload']=dump(protect_class_goals(db,json.loads(item['payload']),id))
        return history

@router.get('/teacher/classes/{id}/students/{student}/profile')
def projection(id:str,student:str,user=Depends(current_user)):
    role(user,'teacher')
    with transaction() as db:
        class_access(db,user,id)
        if not one(db,"SELECT 1 FROM memberships WHERE class_id=:c AND user_id=:u AND status='active'",c=id,u=student): fail(404,'该学生不属于本班')
        return calculate(db,student,id)
