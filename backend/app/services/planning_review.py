"""Explicit evidence boundaries and bounded repair ownership for cloud plan review."""
from app.core.security import fail
from app.services.teaching_packets import candidates,seen_readonly
from app.services.assessment_sessions import question_keys

REVIEW_INSTRUCTION='''审查当前任务的教学正确性，返回approved布尔值、issues字符串数组、findings数组。
四类证据必须分开：
1.sources是授权原文：声称摘录、引用的内容必须受对应原文支持；不能伪造网页或引用。
2.teaching_packet.worked_example是明确给定的项目原创补充素材，可作为独立教学依据，不要求它逐字存在于sources；但仍须检查代码、答案、步骤是否正确、难度与目标是否相符。不得把来源原文没有同一句话本身当成原创示例违规。
3.server_verified.assessments是服务端题库/已见过滤的元数据，只核对任务描述与数量是否一致。题号长短不说明真假，不要求提供未交卷正式题目的答案；规划不预占题，实际领取还会复核。不得把初测证据题号当练习题占位符。
4.learner_evidence是服务端有效测验的掌握画像，probability不是模型猜测；已达标且purpose=review合法。prerequisite_gate.skill_ids=[]表示此任务无先修，不代表缺失本知识点测验证据。
只对含events的调用栈素材检查完整6事件/7快照；普通函数任务无需栈快照。可把原文已有代码分解成清楚的操作步骤，不要求原文事先写出每个步骤的编号，但不能引入不正确的执行顺序。
findings每项含field、skill_id、message，message与对应issues逐项相同。
field只能是instructions（活动描述可改）、citations（引用可改）、fixed_material（项目固定素材错误或难度不符）、server_evidence（服务端数据或规则矛盾）。区分建议与阻断问题：只有实际错误列入issues/findings。
构建智能体只能修instructions/citations，不能改固定素材、题库、成绩、掌握度、先修或预算。固定素材/服务端证据错误应直接标明，不通过反复改写说明掩盖。
approved=true时issues和findings都必须为空；approved=false时两者都非空。硬规则失败必须拒绝。'''


def server_facts(db,state):
    seen=seen_readonly(db,state['actor']['id']);assessments=[]
    for item in state['execution']:
        available=[q['id'] for q in candidates(db,state,item['skill_id']) if not any(key in seen for key in question_keys(q))]
        frozen=item['teaching_packet']['assessment']
        if set(available)!=set(frozen['bank_version_ids']) or len(available)!=frozen['available_count']:
            fail(409,'规划期间题库或已见状态发生变化，请重新生成预览','PLANNING_EVIDENCE_CHANGED')
        assessments.append({'skill_id':item['skill_id'],'available_count':len(available),'question_ids':available,
                            'checked_by':'server-bank-and-exposure-ledger','reserves_question':False})
    return {'contract':'planning-review-evidence-v1','assessments':assessments,
            'mastery_origin':'server-scored-observations','original_examples_origin':'project-authored-supplement',
            'mutable_fields':['instructions','citation_version_ids'],
            'immutable_fields':['teaching_packet','mastery','prerequisites','task_scope','budget']}


def findings(response,allowed_skills):
    items=response.get('findings')
    # Empty successful reviews need no repair ownership; rejected reviews must declare it.
    if items is None and not response['issues']:return []
    if not isinstance(items,list) or len(items)!=len(response['issues']):
        fail(503,'审查问题与修复职责不一致','MODEL_SCHEMA_INVALID')
    for item,message in zip(items,response['issues']):
        if not isinstance(item,dict) or item.get('field') not in ('instructions','citations','fixed_material','server_evidence') or item.get('skill_id') not in allowed_skills or item.get('message')!=message:
            fail(503,'审查问题未绑定有效任务或修复职责','MODEL_SCHEMA_INVALID')
    return items
