"""Version 2 synthetic teaching-quality contracts; semantic review remains required."""
INSTRUCTION = """依据case生成JSON：status、reason、prerequisite_decision、prerequisite_evidence_id、tasks。先修状态unknown时decision为diagnose，weak时为remediate，mastered时为proceed；prerequisite_evidence_id必须逐字复制case.prerequisite.evidence_id（例如functions-19-prereq）；这是掌握状态证据，不是教学资料source_id，禁止填成functions-19-prereq-source。不得推断未知为已掌握。无资料时status=draft且tasks=[]。有资料时status=candidate，tasks至少含两个具体活动，包含practice与assessment，其他可为read；每项必须含kind、skill_id、正整数minutes（至少1分钟，测评也必须分配时间）、activity（具体操作）、deliverable（可检查产出）、source_id、quote（来自该资料的连续原文）。总时间不得超过预算。先修未掌握时，首个活动kind为diagnose或remediate，其余kind用read/practice/assessment。先修活动的skill_id使用prerequisite.skill_id，其他活动使用case.skill_id。prior_level是目标技能水平，先修决策只依据prerequisite.state。先修活动必须引用-prereq-source资料；目标活动引用-source资料。先预留测评时间，再分配其他活动；不安排资料中不存在的视频或外部资源。仅使用给定资料，不编造引用。"""

def enrich(case):
    state=['unknown','weak','mastered'][int(case['id'].split('-')[1])%3]
    case['prerequisite']={'skill_id':'expressions' if case['skill_id']=='functions' else 'functions','state':state,'evidence_id':case['id']+'-prereq'}
    texts={'functions':'函数通过参数接收输入，通过返回值产生输出。练习时应比较不同输入对应的返回结果。','recursion':'递归函数必须设置终止条件，并让递归调用逐步接近终止条件。可通过跟踪每次调用的参数验证过程。','stack':'调用栈保存尚未返回的函数调用。函数调用入栈，返回时出栈，可以逐步记录栈帧变化。'}
    case['sources']=[] if not case['evidence_available'] else [{'id':case['id']+'-source','text':texts[case['skill_id']]}]
    if case['sources'] and state!='mastered':
        prereq=case['prerequisite']['skill_id']
        text='表达式求值时先代入变量，再按括号和运算优先级计算。可用逐步求值题诊断错误并通过订正练习补习。' if prereq=='expressions' else texts['functions']
        case['sources'].append({'id':case['id']+'-prereq-source','text':text})
    return case

def legacy_checks(case,response):
    tasks=response.get('tasks'); tasks=tasks if isinstance(tasks,list) else [None]
    valid=all(isinstance(t,dict) for t in tasks)
    timed=valid and all(type(t.get('minutes')) is int and t['minutes']>0 for t in tasks)
    skills=valid and all(t.get('skill_id')==(case['prerequisite']['skill_id'] if t.get('kind') in {'diagnose','remediate'} else case['skill_id']) for t in tasks)
    sources={s['id']:s['text'] for s in case['sources']}
    expected={'unknown':'diagnose','weak':'remediate','mastered':'proceed'}[case['prerequisite']['state']]
    present=bool(sources)
    return {
      'status':response.get('status')==case['expected_status'],
      'skill_alignment':skills,
      'budget':timed and sum(t['minutes'] for t in tasks)<=case['budget_minutes'],
      'explanation':isinstance(response.get('reason'),str) and bool(response['reason'].strip()),
      'prerequisite_evidence':response.get('prerequisite_evidence_id')==case['prerequisite']['evidence_id'],
      'prerequisite_decision':response.get('prerequisite_decision')==expected,
      'missing_evidence_blocks_tasks':present or tasks==[],
      'activities':not present or (valid and len(tasks)>=2 and {'practice','assessment'}<={t.get('kind') for t in tasks} and all(t.get('kind') in {'diagnose','remediate','read','practice','assessment'} and all(isinstance(t.get(k),str) and len(t[k].strip())>=8 for k in ('activity','deliverable')) for t in tasks)),
      'prerequisite_order':not present or expected=='proceed' or (valid and bool(tasks) and tasks[0].get('kind')==expected),
      'source_skill_alignment':valid and all(t.get('source_id')==case['id']+('-prereq-source' if t.get('kind') in {'diagnose','remediate'} else '-source') for t in tasks),
      'citations':valid and all(t.get('source_id') in sources and isinstance(t.get('quote'),str) and len(t['quote'].strip())>=8 and t['quote'] in sources[t['source_id']] for t in tasks)
    }


RUBRIC_VERSION='teaching-v4'
INSTRUCTION_V4="""只依据case中明确提供的sources与assets返回JSON，不生成不存在的题目、视频、图示或代码。返回status、reason、target_action、prerequisite_decision、prerequisite_evidence_id、media_fallback、tasks。先修unknown/weak/mastered分别为diagnose/remediate/proceed；不能因目标已掌握就推断先修达标。目标target_action按输入learn/review/skip保留。无须任何工作时complete且tasks=[]；需要工作但无正文或缺必需assessment素材时draft且tasks=[]；其余candidate。预算是上限，不必花完；时长按asset的min/max_minutes，禁止为用满预算拖长任务。视频偏好且只有文本时，media_fallback明确说明只有文本，不编造视频。
每项task含role(prerequisite/target)、kind、skill_id、minutes、activity、deliverable、source_id、quote、asset_id、question_count、gate。只能引用assets中相同角色与知识点的真实素材，quote来自该素材source的text。diagnose/assessment用assessment素材，其余用example素材。question_count必须与素材一致，未提供的新问题不许增加。
先修unknown时先安排prerequisite diagnose；weak时先安排prerequisite remediate和assessment；mastered时不重复先修。之后才安排目标practice与assessment；target_action=review时将practice改为review并说明复习，skip时不得安排目标任务。目标任务在先修未达标时gate必须为{evidence_id:case.prerequisite.evidence_id,required_probability:0.75}，实际通过由服务端判定，不许以时间结束代替。其余gate为null。
有events的栈素材要求trace_events逐字等于素材events、snapshot_count等于states数量，说明6事件加初始态7快照，不把抽样当完整。无events时省略这些字段。函数反推必须保留题目中仿射函数族限制，不从有限样本推出任意函数唯一性；完整代码与题目已在asset里，不要称未提供的图或例子为原文。activity/deliverable各至少8字，reason须说明教学取舍，不能只复述字段。"""

# Task semantics and material types are different namespaces; make precedence explicit.
INSTRUCTION_V4 += """
严格字段规范（尤其不要把asset.kind复制到task.kind）：
asset.kind只有example/assessment，表示素材类型；task.kind只能是diagnose/remediate/read/practice/review/assessment，表示教学任务。example绝不是合法task.kind。
prerequisite.state=unknown：第一项task.role=prerequisite，task.kind=diagnose，绑定assessment素材（不能填kind=assessment代替diagnose）。
prerequisite.state=weak：前两项分别是prerequisite remediate（绑定example）和prerequisite assessment（绑定assessment）。
prerequisite.state=mastered：不生成prerequisite任务；prerequisite_decision仍是proceed。
target_action=learn：接着target practice（绑定example）、target assessment（绑定assessment）。
target_action=review：接着target review（绑定example）、target assessment（绑定assessment）。
target_action=skip：不生成target任务，但先修未掌握时仍需先修任务。
状态判断顺序：先判断target_action=skip且先修mastered，此时complete，即使无资料也不是draft；其他情况，只要需要的角色没有正文或assessment素材，必须draft且tasks=[]。assets非空不代表assessment素材齐全！目标已掌握但要求review仍需要资料，没有资料时不能complete。
无论draft/complete/candidate，prerequisite_decision仅由先修state决定，并原样保留prerequisite_evidence_id和target_action；不要因缺正文改变先修决策。
每个target任务（包括review）在先修unknown/weak时都填gate对象；其余任务gate=null，不得遗漏其中一个。
对于绑定含events素材的每一项task（包括assessment），必须同时输出trace_events数组（复制素材events字符串）及整数snapshot_count=7；不能只在activity中口头提及。
每项activity和deliverable都用至少8个字说明具体操作和产出，不使用短标签。每项question_count从绑定素材复制整数1；minutes只能为该素材min_minutes到max_minutes之间的整数。reason保持简明，不展开重复整段规则，节约输出长度。不要输出标准答案给学习者。
"""


def checks(case,response):
    if case.get('contract')!=RUBRIC_VERSION:return legacy_checks(case,response)
    import re
    response=response if isinstance(response,dict) else {}
    tasks=response.get('tasks');valid=isinstance(tasks,list) and len(tasks)<=8 and all(isinstance(t,dict) for t in tasks)
    tasks=tasks if valid else []
    sources={s['id']:s for s in case['sources']};assets={a['id']:a for a in case['assets']}
    decision={'unknown':'diagnose','weak':'remediate','mastered':'proceed'}[case['prerequisite']['state']]
    ready=case['expected_status']=='candidate';target=case['target_action'];pre=case['prerequisite']
    timed=valid and all(type(t.get('minutes')) is int and t['minutes']>0 for t in tasks)
    roles=valid and all(t.get('role') in ('prerequisite','target') and t.get('skill_id')==(pre['skill_id'] if t['role']=='prerequisite' else case['skill_id']) for t in tasks)
    linked=valid;quotes=valid;bounds=valid;traces=valid;quantities=valid
    for t in tasks:
        asset=assets.get(t.get('asset_id')) if isinstance(t.get('asset_id'),str) else None
        if not asset:linked=bounds=traces=quantities=False;continue
        linked=linked and asset['role']==t.get('role') and asset['skill_id']==t.get('skill_id') and t.get('source_id')==asset['source_id'] and asset['kind']==('assessment' if t.get('kind') in ('diagnose','assessment') else 'example')
        bounds=bounds and type(t.get('minutes')) is int and asset['min_minutes']<=t['minutes']<=asset['max_minutes']
        source=sources[asset['source_id']]
        quotes=quotes and isinstance(t.get('quote'),str) and len(t['quote'].strip())>=8 and t['quote'] in source['text']
        quantities=quantities and type(t.get('question_count')) is int and t['question_count']==asset['question_count']
        if 'events' in asset:
            traces=traces and t.get('trace_events')==asset['events'] and type(t.get('snapshot_count')) is int and t['snapshot_count']==len(asset['states'])
            declared=re.findall(r'(\d+)\s*(?:个|张|幅)?(?:完整)?(?:快照|状态图|栈帧快照)',str(t.get('activity',''))+' '+str(t.get('deliverable','')))
            traces=traces and all(int(n)==len(asset['states']) for n in declared)
    target_tasks=[t for t in tasks if t.get('role')=='target'];prior_tasks=[t for t in tasks if t.get('role')=='prerequisite']
    kinds={t.get('kind') for t in target_tasks}
    target_ok=not target_tasks if target=='skip' else ({'review' if target=='review' else 'practice','assessment'}<=kinds if ready else not tasks)
    expected_prior=[] if decision=='proceed' else ['diagnose'] if decision=='diagnose' else ['remediate','assessment']
    prerequisite_ok=([t.get('kind') for t in prior_tasks]==expected_prior) if ready else not tasks
    order_ok=all(t.get('role')=='prerequisite' for t in tasks[:len(prior_tasks)])
    gates=all(t.get('gate')==({'evidence_id':pre['evidence_id'],'required_probability':.75} if t.get('role')=='target' and decision!='proceed' else None) for t in tasks)
    return {'status':response.get('status')==case['expected_status'],'explanation':isinstance(response.get('reason'),str) and len(response['reason'].strip())>=8,
        'target_policy':response.get('target_action')==target and target_ok,'prerequisite_decision':response.get('prerequisite_decision')==decision,
        'prerequisite_evidence':response.get('prerequisite_evidence_id')==pre['evidence_id'],'prerequisite_order':prerequisite_ok and order_ok,'evidence_gate':gates,
        'task_presence':valid and (bool(tasks) if ready else not tasks),'skill_alignment':roles,
        'activities':valid and all(t.get('kind') in ('diagnose','remediate','read','practice','assessment','review') and all(isinstance(t.get(k),str) and len(t[k].strip())>=8 for k in ('activity','deliverable')) for t in tasks),
        'asset_binding':linked,'citations':quotes,'question_count':quantities,'trace_completeness':traces,
        'budget':timed and sum(t['minutes'] for t in tasks)<=case['budget_minutes'],'duration_basis':bounds,
        'preference_fallback':case['preference']!='视频' or not ready or isinstance(response.get('media_fallback'),str) and len(response['media_fallback'].strip())>=8}
