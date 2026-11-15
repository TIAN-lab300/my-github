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

def checks(case,response):
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
