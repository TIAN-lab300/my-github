"""Server-owned teaching packets: explicit source refs, examples, gates and real bank readiness."""
import json,re
from app.core.db import rows,one
from app.services.assessment_sessions import question_keys
from app.services.teaching_examples import PLANNING_EXAMPLES
CONTRACT='execution-v1'

def seen_readonly(db,student):
    keys={r['identity'] for r in rows(db,'SELECT identity FROM question_exposures WHERE student_id=:u',u=student)}
    for record in rows(db,'SELECT questions FROM diagnoses WHERE student_id=:u',u=student)+rows(db,'SELECT questions FROM assessment_sessions WHERE student_id=:u',u=student)+rows(db,'SELECT t.questions FROM tasks t JOIN assignments a ON a.task_id=t.id WHERE a.student_id=:u',u=student):
        for q in json.loads(record['questions']):keys.update(question_keys(q))
    for item in rows(db,'SELECT i.snapshot FROM learning_assessment_items i JOIN learning_assessments a ON a.id=i.assessment_id WHERE a.student_id=:u',u=student):
        q=json.loads(item['snapshot']);keys.update(question_keys(q))
    return keys

def candidates(db,state,skill):
    from app.services.topic_bank import question_bank
    from app.services.course_planning import binding,bank as course_bank
    from app.services.engineering_goals import context,bank as project_bank
    published=[]
    for row in rows(db,"SELECT * FROM bank_versions WHERE status='published' ORDER BY created_at,id"):
        q=json.loads(row['content'])
        if q['skill']==skill and q['purpose'] in ('both','practice'):published.append({**q,'id':row['id'],'question_id':row['question_id']})
    bank=published or [q for q in question_bank(db,'practice',state['graph_version'] if state['graph_version']!='curated-v1' else None)[0] if q['skill']==skill]
    cb=binding(db,state['goal']['id'])
    if cb:bank=course_bank(db,cb,'practice',{skill})
    pc=context(db,state['goal']['id'])
    if pc:bank=[q for q in project_bank(db,pc['graph_version'],'practice') if q['skill']==skill]
    return bank

def attach_packets(db,state):
    seen=seen_readonly(db,state['actor']['id']);warnings=[]
    for item in state['execution']:
        skill=item['skill_id'];bank=candidates(db,state,skill)
        eligible=[q for q in bank if not any(key in seen for key in question_keys(q))]
        refs=[{'resource_id':s['resource_id'],'version_id':s['version_id'],'title':s['title']} for s in state['sources'] if skill in s['supported_skills']]
        alias=skill if state['graph_version']=='curated-v1' else skill.removeprefix('catalog:project-python-foundations-') if skill.startswith('catalog:project-python-foundations-') else None
        example=PLANNING_EXAMPLES.get(alias)
        # Global curated IDs may only use Python examples, never infer a C++ identity by its title.
        from app.services.course_planning import binding
        cb=binding(db,state['goal']['id'])
        if cb and cb['course_id']!='project-python-foundations':example=None
        packet={'contract':CONTRACT,'purpose':'review' if item.get('kind')=='review' else 'learning',
            'reading':{'sources':refs,'instruction':'阅读所列具体版本中涉及当前知识点的定义与例子；不要求原文未提供的条件、图示或摘录。'},
            'worked_example':{'origin':'本项目单独提供的原创示例，不声称摘自引用正文','example_id':'project-python-'+alias+'-runtime-v2','version':'runtime-examples-v2',**example} if example else None,
            'deliverable':'写出输入、逐步过程、输出与依据；示例演算不计入掌握度，正式测验由服务端判分。',
            'assessment':{'available_count':len(eligible),'question_count':1 if eligible else 0,'bank_version_ids':[q['id'] for q in eligible],
                'instruction':'点击知识测验领取1道真实新题；领取时重新核验题库状态、已见记录与权限。' if eligible else '当前无可用新题，先阅读与演算；请教师补题后再测验，不能生成或伪造试卷。'},
            'prerequisite_gate':{'skill_ids':item['prerequisites'],'required_probability':.75,'decision_source':'服务端有效测验证据，不以完成时长替代'},
            'media_note':'当前按已有正文学习；未关联可观看视频时不声称满足视频偏好。' if state['goal'].get('preference')=='video' else None}
        item['teaching_packet']=packet
        item['assessment']='领取1道正式新题，服务端判分并核验先修；实际可用性以领取时为准' if eligible else '当前新题不足：先阅读与示例演算，测验待补齐，不视为已掌握'
        if not eligible:warnings.append(item['name']+'：缺少可用新测验题，阅读/示例可用，测验待补齐')
    state['execution_contract']=CONTRACT;state['teaching_warnings']=warnings

def packet_valid(item):
    p=item.get('teaching_packet',{});a=p.get('assessment',{})
    return p.get('contract')==CONTRACT and p.get('purpose')==('review' if item.get('kind')=='review' else 'learning') and bool(p.get('reading',{}).get('sources')) and type(a.get('available_count')) is int and a['available_count']>=0 and a.get('question_count')==(1 if a['available_count'] else 0) and len(a.get('bank_version_ids',[]))==a['available_count'] and p.get('prerequisite_gate',{}).get('skill_ids')==item['prerequisites']

def model_claim_issues(item):
    packet=item.get('teaching_packet',{});text=item.get('instructions','');issues=[]
    maximum=packet.get('assessment',{}).get('question_count',0)
    numerals={'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10}
    for raw in re.findall(r'(\d+|[一二三四五六七八九十])\s*(?:道|题)',text):
        number=int(raw) if raw.isdigit() else numerals[raw]
        if number>maximum:issues.append(item['skill_id']+'：描述题量超过本次可领取题数，必须按teaching_packet标明真实题量或待补题')
    example=packet.get('worked_example') or {}
    if example.get('events'):
        for count in re.findall(r'(\d+)\s*(?:个|张|幅)?(?:完整)?(?:快照|状态图|栈帧快照)',text):
            if int(count)!=len(example['states']):issues.append(item['skill_id']+'：完整示例为6事件/7快照，不能压成不完整固定快照；抽样须明确限定')
    if not example and any(word in text for word in ('摘录示例','原文中的图示','原文提供的代码')):issues.append(item['skill_id']+'：未提供对应示例/图示，不得假称原文已有')
    return list(dict.fromkeys(issues))
