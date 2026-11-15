"""A normalized learning and single-choice assessment workflow, isolated from legacy goals."""
import json
from collections import defaultdict
from typing import Literal
from pydantic import BaseModel,Field,StrictInt
from fastapi import APIRouter,Depends
from app.core.db import transaction,one,rows,run,insert,uid,now,dump,audit
from app.core.security import current_user,role,fail,resource_access
from app.services.learning import bkt
router=APIRouter()

class Chapter(BaseModel):
    title:str=Field(min_length=1,max_length=200)
    position:int=Field(ge=0,le=1000)
    skill_ids:list[str]=Field(min_length=1,max_length=100)

@router.post('/learning/courses/{id}/chapters',status_code=201)
def chapter(id:str,body:Chapter,user=Depends(current_user)):
    role(user,'admin')
    with transaction() as db:
        course(db,id)
        if one(db,'SELECT id FROM learning_chapters WHERE course_id=:c AND position=:p',c=id,p=body.position):fail(409,'章节顺序已被占用')
        for sid in body.skill_ids:
            skill(db,id,sid)
            if one(db,'SELECT skill_id FROM learning_skill_chapters WHERE skill_id=:s',s=sid):fail(409,'知识点已关联章节')
        if len(set(body.skill_ids))!=len(body.skill_ids):fail(422,'知识点不能重复')
        ident=uid();insert(db,'learning_chapters',id=ident,course_id=id,title=body.title,position=body.position)
        for sid in body.skill_ids:insert(db,'learning_skill_chapters',skill_id=sid,chapter_id=ident,course_id=id)
        audit(db,user['id'],'learning_chapter_created',ident)
    return {'id':ident}

def course(db,ident):
    c=one(db,'SELECT * FROM curriculum_catalog_courses WHERE id=:i',i=ident)
    if not c:fail(404,'课程不存在')
    return c

def skill(db,cid,sid):
    s=one(db,'SELECT * FROM curriculum_catalog_skills WHERE course_id=:c AND id=:s',c=cid,s=sid)
    if not s:fail(422,'知识点不属于所选课程')
    return s

def material(db,user,ident):
    link=one(db,'SELECT * FROM learning_material_links WHERE id=:i',i=ident)
    if not link:fail(404,'学习资料关联不存在')
    r=resource_access(db,user,link['resource_id'])
    v=one(db,'SELECT * FROM resource_versions WHERE id=:v AND resource_id=:r',v=link['resource_version_id'],r=r['id'])
    if r['status']!='published' or r['current_version']!=v['id'] or v['parse_status']!='ready':
        fail(409,'关联资料已撤回或更新，请重新关联当前有效版本')
    return link

class Question(BaseModel):
    course_id:str
    skill_id:str
    prompt:str=Field(min_length=1,max_length=4000)
    options:list[str]=Field(min_length=2,max_length=8)
    answer:StrictInt
    explanation:str=Field(min_length=1,max_length=4000)
    phase:Literal['diagnostic','practice','retest']='practice'
    source:str=Field(min_length=1,max_length=2000)

@router.post('/learning/questions',status_code=201)
def create_question(body:Question,user=Depends(current_user)):
    role(user,'admin')
    if not body.prompt.strip() or not body.explanation.strip() or not body.source.strip() or any(not x.strip() for x in body.options) or len(set(body.options))!=len(body.options) or not 0<=body.answer<len(body.options):fail(422,'题干、选项、答案或解析不合法')
    with transaction() as db:
        skill(db,body.course_id,body.skill_id)
        qid=uid();vid=uid()
        insert(db,'learning_questions',id=qid,course_id=body.course_id,owner_id=user['id'],created_at=now())
        insert(db,'learning_question_versions',id=vid,question_id=qid,course_id=body.course_id,skill_id=body.skill_id,version=1,phase=body.phase,prompt=body.prompt.strip(),options=dump(body.options),answer=body.answer,explanation=body.explanation.strip(),source=body.source,created_at=now())
        audit(db,user['id'],'learning_question_drafted',vid)
    return {'id':vid,'status':'draft'}

class Review(BaseModel):
    confirmed:bool

@router.post('/learning/questions/{id}/publish')
def publish_question(id:str,body:Review,user=Depends(current_user)):
    role(user,'admin')
    if not body.confirmed:fail(422,'请确认已核对完整题目、答案、来源许可及知识点')
    with transaction() as db:
        q=one(db,'SELECT * FROM learning_question_versions WHERE id=:i',i=id)
        if not q or q['status']!='draft':fail(409,'只能发布草稿题目')
        c=course(db,q['course_id'])
        if c['assessment_mode']=='project_rubric':fail(409,'实践项目不能以选择题作为最终验收')
        run(db,"UPDATE learning_question_versions SET status='published',reviewer_id=:u WHERE id=:i",u=user['id'],i=id)
        audit(db,user['id'],'learning_question_published',id)
    return {'ok':True}

@router.post('/learning/questions/{id}/disable')
def disable_question(id:str,user=Depends(current_user)):
    role(user,'admin')
    with transaction() as db:
        if not one(db,'SELECT id FROM learning_question_versions WHERE id=:i',i=id):fail(404,'题目不存在')
        run(db,"UPDATE learning_question_versions SET status='disabled' WHERE id=:i",i=id)
        audit(db,user['id'],'learning_question_disabled',id)
    return {'ok':True}

class MaterialLink(BaseModel):
    skill_id:str
    resource_id:str
    locator:str=Field(default='',max_length=1000)

@router.post('/learning/courses/{id}/materials',status_code=201)
def link_material(id:str,body:MaterialLink,user=Depends(current_user)):
    role(user,'admin')
    with transaction() as db:
        skill(db,id,body.skill_id);r=resource_access(db,user,body.resource_id)
        v=one(db,'SELECT * FROM resource_versions WHERE id=:v',v=r['current_version'])
        if r['scope']!='school' or r['status']!='published' or not v or v['parse_status']!='ready' or not v['body'].strip():fail(409,'请选择校级已发布且正文可用的资料；外链导读不属于正式教学正文')
        old=one(db,'SELECT id FROM learning_material_links WHERE skill_id=:s AND resource_version_id=:v',s=body.skill_id,v=v['id'])
        if old:return {'id':old['id']}
        ident=uid();insert(db,'learning_material_links',id=ident,course_id=id,skill_id=body.skill_id,resource_id=r['id'],resource_version_id=v['id'],locator=body.locator)
        audit(db,user['id'],'learning_material_linked',ident)
    return {'id':ident}

@router.get('/learning/courses/{id}')
def learning_course(id:str,user=Depends(current_user)):
    with transaction() as db:
        c=course(db,id);c['skills']=rows(db,'SELECT id,name,status FROM curriculum_catalog_skills WHERE course_id=:c ORDER BY id',c=id)
        c['chapters']=rows(db,'SELECT * FROM learning_chapters WHERE course_id=:c ORDER BY position',c=id)
        for s in c['skills']:
            s['materials']=[]
            for link in rows(db,'SELECT m.*,r.title FROM learning_material_links m JOIN resources r ON r.id=m.resource_id JOIN resource_versions v ON v.id=m.resource_version_id WHERE m.skill_id=:s AND r.scope=\'school\' AND r.status=\'published\' AND r.current_version=v.id AND v.parse_status=\'ready\'',s=s['id']):s['materials'].append(link)
            s['question_counts']={p:one(db,"SELECT COUNT(DISTINCT question_id) n FROM learning_question_versions WHERE skill_id=:s AND phase=:p AND status='published'",s=s['id'],p=p)['n'] for p in ('diagnostic','practice','retest')}
        if user['role']=='admin':c['question_drafts']=rows(db,"SELECT id,skill_id,prompt,status,phase FROM learning_question_versions WHERE course_id=:c ORDER BY created_at DESC",c=id)
    return c

class Study(BaseModel):
    session_id:str=Field(min_length=1,max_length=100)
    minutes:int=Field(ge=1,le=1440)
    note:str=Field(default='',max_length=1000)

@router.post('/learning/materials/{id}/study')
def study(id:str,body:Study,user=Depends(current_user)):
    role(user,'student')
    with transaction() as db:
        material(db,user,id)
        existing=one(db,'SELECT * FROM learning_sessions WHERE id=:i',i=body.session_id)
        if existing and (existing['student_id']!=user['id'] or existing['material_link_id']!=id):fail(409,'学习会话标识冲突')
        if existing:run(db,'UPDATE learning_sessions SET minutes=:m,note=:n WHERE id=:i',m=body.minutes,n=body.note,i=body.session_id)
        else:insert(db,'learning_sessions',id=body.session_id,student_id=user['id'],material_link_id=id,minutes=body.minutes,note=body.note,created_at=now())
    return {'ok':True,'message':'学习记录已保存；学习时长不直接提高掌握度'}

class Paper(BaseModel):
    course_id:str
    skill_ids:list[str]=Field(min_length=1,max_length=30)
    phase:Literal['diagnostic','practice','retest']='practice'
    per_skill:int=Field(default=2,ge=1,le=5)

@router.post('/learning/assessments',status_code=201)
def create_paper(body:Paper,user=Depends(current_user)):
    role(user,'student')
    if len(set(body.skill_ids))!=len(body.skill_ids):fail(422,'知识点不能重复')
    with transaction() as db:
        if course(db,body.course_id)['assessment_mode']=='project_rubric':fail(409,'该课程以项目成果及教师量规评价，不能生成替代验收的选择题试卷')
        chosen=[];missing=[]
        for sid in body.skill_ids:
            skill(db,body.course_id,sid)
            candidates=rows(db,"SELECT v.* FROM learning_question_versions v WHERE course_id=:c AND skill_id=:s AND phase=:p AND status='published' AND NOT EXISTS (SELECT 1 FROM learning_question_versions newer WHERE newer.question_id=v.question_id AND newer.status='published' AND newer.version>v.version) ORDER BY question_id",c=body.course_id,s=sid,p=body.phase)
            if body.phase=='retest':
                # Previous display counts as exposure, even without a submitted answer.
                exposed={r['question_id'] for r in rows(db,'SELECT v.question_id FROM learning_assessment_items i JOIN learning_assessments a ON a.id=i.assessment_id JOIN learning_question_versions v ON v.id=i.question_version_id WHERE a.student_id=:u',u=user['id'])}
                candidates=[q for q in candidates if q['question_id'] not in exposed]
            if len(candidates)<body.per_skill:missing.append(sid)
            chosen+=candidates[:body.per_skill]
        if missing:fail(409,'题库覆盖不足或重测题已公开：'+', '.join(missing),'QUESTION_COVERAGE_GAP')
        ident=uid();insert(db,'learning_assessments',id=ident,student_id=user['id'],course_id=body.course_id,phase=body.phase,created_at=now())
        for position,q in enumerate(chosen):insert(db,'learning_assessment_items',id=uid(),assessment_id=ident,question_version_id=q['id'],skill_id=q['skill_id'],position=position,snapshot=dump(q))
    return {'id':ident}

def owned(db,user,id):
    a=one(db,'SELECT * FROM learning_assessments WHERE id=:i AND student_id=:u',i=id,u=user['id'])
    if not a:fail(404,'试卷不存在')
    return a

@router.get('/learning/assessments/{id}')
def paper(id:str,user=Depends(current_user)):
    with transaction() as db:
        a=owned(db,user,id);items=rows(db,'SELECT * FROM learning_assessment_items WHERE assessment_id=:i ORDER BY position',i=id)
        a['questions']=[]
        for item in items:
            q=json.loads(item['snapshot']);public={'id':item['id'],'skill_id':item['skill_id'],'prompt':q['prompt'],'options':json.loads(q['options'])}
            if a['status']=='submitted':public.update(answer=q['answer'],explanation=q['explanation'],source=q['source'])
            a['questions'].append(public)
        a['draft_answers']=json.loads(a['draft_answers'])
        if a['status']=='submitted':
            a['evaluation']=one(db,'SELECT * FROM learning_evaluations WHERE assessment_id=:i',i=id)
            a['skill_evaluations']=rows(db,'SELECT * FROM learning_skill_evaluations WHERE assessment_id=:i',i=id)
    return a

class Answers(BaseModel):
    answers:dict[str,StrictInt]

def validate_answers(items,answers,partial=False):
    ids={i['id'] for i in items}
    if not set(answers)<=ids or (not partial and set(answers)!=ids):fail(422,'请完成所有题目，不能提交额外题号')
    for item in items:
        if item['id'] in answers and not 0<=answers[item['id']]<len(json.loads(json.loads(item['snapshot'])['options'])):fail(422,'选项超出范围')

@router.put('/learning/assessments/{id}/draft')
def save_draft(id:str,body:Answers,user=Depends(current_user)):
    with transaction() as db:
        if owned(db,user,id)['status']!='open':fail(409,'已交卷，不能修改')
        items=rows(db,'SELECT * FROM learning_assessment_items WHERE assessment_id=:i',i=id);validate_answers(items,body.answers,True)
        run(db,'UPDATE learning_assessments SET draft_answers=:a WHERE id=:i',a=dump(body.answers),i=id)
    return {'ok':True}

@router.post('/learning/assessments/{id}/submit')
def submit(id:str,body:Answers,user=Depends(current_user)):
    with transaction() as db:
        a=owned(db,user,id)
        if a['status']=='submitted':
            if json.loads(a['draft_answers'])!=body.answers:fail(409,'已交卷，答案不能更改')
            return {'ok':True,'already_submitted':True}
        items=rows(db,'SELECT * FROM learning_assessment_items WHERE assessment_id=:i ORDER BY position',i=id);validate_answers(items,body.answers)
        groups=defaultdict(list)
        for item in items:
            q=one(db,'SELECT status FROM learning_question_versions WHERE id=:i',i=item['question_version_id'])
            if not q or q['status']!='published':fail(409,'试卷中存在停用题目，请重新组卷')
            snapshot=json.loads(item['snapshot']);correct=int(body.answers[item['id']]==snapshot['answer'])
            insert(db,'learning_responses',item_id=item['id'],selected_option=body.answers[item['id']],correct=correct);groups[item['skill_id']].append(correct)
        for sid,values in groups.items():
            old=one(db,'SELECT e.probability,e.evidence_count FROM learning_skill_evaluations e JOIN learning_assessments a ON a.id=e.assessment_id WHERE a.student_id=:u AND e.skill_id=:s ORDER BY a.submitted_at DESC,a.rowid DESC LIMIT 1',u=user['id'],s=sid)
            probability=old['probability'] if old else .2
            for correct in values:probability=bkt(probability,bool(correct))
            insert(db,'learning_skill_evaluations',assessment_id=id,skill_id=sid,correct_count=sum(values),total_count=len(values),probability=probability,evidence_count=(old['evidence_count'] if old else 0)+len(values))
        correct=sum(sum(v) for v in groups.values());insert(db,'learning_evaluations',assessment_id=id,correct_count=correct,total_count=len(items),score=100*correct/len(items),rule_version='single-choice-v1/bkt-v1',created_at=now())
        run(db,"UPDATE learning_assessments SET status='submitted',draft_answers=:a,submitted_at=:t WHERE id=:i",a=dump(body.answers),t=now(),i=id)
        audit(db,user['id'],'learning_assessment_submitted',id)
    return {'ok':True}

@router.get('/learning/courses/{id}/progress')
def progress(id:str,user=Depends(current_user)):
    role(user,'student')
    with transaction() as db:
        course(db,id)
        result=rows(db,'SELECT id,name FROM curriculum_catalog_skills WHERE course_id=:c ORDER BY id',c=id)
        for s in result:
            s['study_minutes']=one(db,'SELECT COALESCE(SUM(l.minutes),0) n FROM learning_sessions l JOIN learning_material_links m ON m.id=l.material_link_id WHERE l.student_id=:u AND m.skill_id=:s',u=user['id'],s=s['id'])['n']
            s['evaluation']=one(db,'SELECT e.* FROM learning_skill_evaluations e JOIN learning_assessments a ON a.id=e.assessment_id WHERE a.student_id=:u AND e.skill_id=:s ORDER BY a.submitted_at DESC,a.rowid DESC LIMIT 1',u=user['id'],s=s['id'])
        history=rows(db,'SELECT a.id,a.phase,a.status,a.created_at,e.score FROM learning_assessments a LEFT JOIN learning_evaluations e ON e.assessment_id=a.id WHERE a.student_id=:u AND a.course_id=:c ORDER BY a.created_at DESC',u=user['id'],c=id)
    return {'skills':result,'assessments':history}
