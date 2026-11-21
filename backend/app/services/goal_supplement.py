"""Generate missing curriculum material as explicit, unpublished proposal drafts."""
import json
from app.core.db import transaction,one,run,dump,audit
from app.core.security import fail
from app.services.engineering_goals import model_call


def generate(proposal_id,user):
    with transaction() as db:
        p=one(db,'SELECT * FROM project_goal_proposals WHERE id=:i AND student_id=:u',i=proposal_id,u=user['id'])
        if not p:fail(404,'目标解析提案不存在')
        analysis=json.loads(p['analysis'])
    response,config=model_call('GoalDiagnosisAgent',{'operation':'missing-curriculum-draft-v1','goal':p['description'],
        'matched_skills':analysis.get('skills',[]),'missing':analysis.get('uncovered_capabilities',[]),
        'output':{'units':[{'course':'课程名','chapter':'章节名','knowledge':'知识点名','prerequisites':['前置知识名称'],'body':'中文原创教学正文，200至8000字','questions':[{'phase':'diagnostic/practice/retest','prompt':'完整题干','options':['选项'],'answer':0,'explanation':'答案解释'}]}]},
        'instruction':'分析工程需要的真实能力，补充缺失课程章节知识点、原创中文正文及测验草稿，最多6个单元每单元最多3题。现有数据仅作参考，不固定使用Python函数递归调用栈。没有真实外部来源不得捏造链接。所有内容为AI生成待审核，不声称已发布或学生已掌握。'})
    units=response.get('units') if isinstance(response,dict) else None
    if not isinstance(units,list) or not 1<=len(units)<=6:fail(503,'补充单元格式错误','MODEL_SCHEMA_INVALID')
    for unit in units:
        for key,limit in [('course',200),('chapter',200),('knowledge',200),('body',8000)]:
            if not isinstance(unit.get(key),str) or not unit[key].strip() or len(unit[key])>limit:fail(503,'补充字段错误：'+key,'MODEL_SCHEMA_INVALID')
        if len(unit['body'])<200:fail(503,'补充正文不足200字','MODEL_SCHEMA_INVALID')
        if not isinstance(unit.get('prerequisites'),list) or len(unit['prerequisites'])>12 or any(not isinstance(v,str) or len(v)>200 for v in unit['prerequisites']):fail(503,'先修格式错误','MODEL_SCHEMA_INVALID')
        qs=unit.get('questions')
        if not isinstance(qs,list) or not 1<=len(qs)<=3:fail(503,'补充题目格式错误','MODEL_SCHEMA_INVALID')
        for q in qs:
            opts=q.get('options',[]) if isinstance(q,dict) else []
            if not isinstance(opts,list) or not 2<=len(opts)<=6 or any(not isinstance(o,str) or not o.strip() or len(o)>1000 for o in opts) or len(set(opts))!=len(opts) or type(q.get('answer')) is not int or not 0<=q['answer']<len(opts):fail(503,'题目选项答案格式错误','MODEL_SCHEMA_INVALID')
            if q.get('phase') not in ('diagnostic','practice','retest') or any(not isinstance(q.get(k),str) or not q[k].strip() or len(q[k])>4000 for k in ('prompt','explanation')):fail(503,'题干解释格式错误','MODEL_SCHEMA_INVALID')
    with transaction() as db:
        current=one(db,'SELECT analysis FROM project_goal_proposals WHERE id=:i AND student_id=:u',i=proposal_id,u=user['id'])
        if not current:fail(404,'解析提案已删除')
        saved=json.loads(current['analysis']);saved['supplement_draft']={'status':'pending_review','origin':'model_generated','model_config_id':config,'units':units}
        run(db,'UPDATE project_goal_proposals SET analysis=:a WHERE id=:i',a=dump(saved),i=proposal_id)
        audit(db,user['id'],'goal_supplement_generated',proposal_id)
    return {'status':'pending_review','units':[{'course':u['course'],'chapter':u['chapter'],'knowledge':u['knowledge'],'body':u['body'],'question_count':len(u['questions'])} for u in units],
        'message':'补充草稿已保存；未经审核不作为正式课程证据或诊断题，答案不返回学生。'}
