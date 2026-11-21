from pathlib import Path
import json
from fastapi import APIRouter,Depends
from fastapi.responses import FileResponse
from app.core.db import transaction,one,rows,run,audit,DATA
from app.core.security import current_user,role,fail
from app.services import project_delivery as service

router=APIRouter()

@router.get('/engineering-goals/{id}/workspace')
def workspace(id:str,user=Depends(current_user)):return service.workspace(id,user)

@router.put('/engineering-goals/{id}/workspace')
def save(id:str,body:dict,user=Depends(current_user)):return service.save_spec(id,user,body)


@router.post('/engineering-goals/{id}/milestones/{milestone}/submissions',status_code=201)
def submit(id:str,milestone:str,body:dict,user=Depends(current_user)):return service.submit(id,milestone,user,body)

@router.post('/project-deliveries/{id}/review')
def review(id:str,body:dict,user=Depends(current_user)):return service.review(id,user,body)

@router.get('/project-deliveries/review-inbox')
def inbox(user=Depends(current_user)):
    role(user,'teacher','admin')
    with transaction() as db:
        records=rows(db,"SELECT d.id,d.created_at,m.goal_id,m.milestone_key,g.title,g.student_id,g.class_id,u.name student_name FROM project_deliveries d JOIN project_milestones m ON m.id=d.milestone_id JOIN goals g ON g.id=m.goal_id JOIN users u ON u.id=g.student_id JOIN project_delivery_plans p ON p.id=d.plan_id WHERE d.status='pending' AND p.status='active' AND g.status!='archived' ORDER BY d.created_at")
        return [r for r in records if user['role']=='admin' or r['class_id'] and one(db,'SELECT id FROM classes WHERE id=:c AND owner_id=:u',c=r['class_id'],u=user['id'])]

@router.get('/project-deliveries/{id}/artifacts/{resource}/download')
def artifact(id:str,resource:str,user=Depends(current_user)):
    with transaction() as db:
        delivery=one(db,'SELECT * FROM project_deliveries WHERE id=:d',d=id)
        if not delivery:fail(404,'提交不存在')
        m=one(db,'SELECT goal_id FROM project_milestones WHERE id=:m',m=delivery['milestone_id']);service.access(db,user,m['goal_id'])
        selected=next((a for a in json.loads(delivery['evidence'])['artifacts'] if a['resource_id']==resource),None)
        if not selected:fail(404,'附件不属于本次提交')
        version=one(db,'SELECT storage_key,mime,filename,hash FROM resource_versions WHERE id=:v AND resource_id=:r',v=selected['version_id'],r=resource)
        if not version or version['hash']!=selected['sha256']:fail(409,'冻结附件版本已变化')
        file=(DATA/'files'/version['storage_key']).resolve()
        if not file.is_relative_to((DATA/'files').resolve()) or not file.is_file():fail(404,'附件文件不存在')
    return FileResponse(file,filename=version['filename'],media_type=version['mime'],content_disposition_type='attachment')

@router.get('/project-material-pack/{name}')
def material(name:str,user=Depends(current_user)):
    names={'guide.md','triangle.vert','triangle.frag','checklist.md'}
    if name not in names:fail(404,'起步资料不存在')
    file=Path(__file__).resolve().parents[3]/'docs/curriculum/opengl-project'/name
    return FileResponse(file,filename=name,media_type='text/plain',content_disposition_type='attachment')
