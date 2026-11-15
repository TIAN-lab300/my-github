"""Strict bounded output contracts for the four planning agents."""
from app.core.security import fail

def validate_output(agent,response):
    def reject():fail(503,'智能体输出字段缺失、类型错误或超过长度限制','MODEL_SCHEMA_INVALID')
    def text(value,limit):return isinstance(value,str) and bool(value.strip()) and len(value)<=limit
    def strings(value):return isinstance(value,list) and len(value)<=20 and all(text(x,500) for x in value)
    if not isinstance(response,dict):reject()
    if agent=='GoalDiagnosisAgent':
        if not text(response.get('summary'),2000) or not strings(response.get('risks')):reject()
    elif agent=='LearningReplanAgent':
        if not text(response.get('reason'),2000) or not strings(response.get('recommendations')):reject()
    elif agent=='PlanReviewAgent':
        if type(response.get('approved')) is not bool or not strings(response.get('issues')):reject()
        if response['approved'] and response['issues']:reject()
    elif agent=='PathBuildingAgent':
        tasks=response.get('tasks')
        if not text(response.get('reason'),2000) or not isinstance(tasks,list) or len(tasks)>30:reject()
        for task in tasks:
            if not isinstance(task,dict) or not text(task.get('skill_id'),100) or not text(task.get('instructions'),4000):reject()
            if type(task.get('minutes')) is not int or not 1<=task['minutes']<=1440:reject()
            refs=task.get('citation_version_ids')
            if not isinstance(refs,list) or not 1<=len(refs)<=8 or not all(text(x,100) for x in refs) or len(set(refs))!=len(refs):reject()
    else:reject()
    return response
