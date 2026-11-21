"""Strict bounded output contracts with field-level feedback for model repair."""
from app.core.security import fail


def validate_output(agent,response):
    # Exact legacy alias only; never invent a reason or replace an invalid canonical field.
    field={'PathBuildingAgent':'reason','LearningReplanAgent':'reason','GoalDiagnosisAgent':'summary'}.get(agent)
    if isinstance(response,dict) and field and field not in response and isinstance(response.get('summary_or_reason'),str):
        response[field]=response['summary_or_reason']
    def reject(field,requirement):fail(503,agent+' 输出不符合约定：'+field+' '+requirement,'MODEL_SCHEMA_INVALID')
    def text(value,limit):return isinstance(value,str) and bool(value.strip()) and len(value)<=limit
    def require_text(value,field,limit):
        if not text(value,limit):reject(field,'必须为非空字符串，最多'+str(limit)+'字')
    def strings(value,field):
        if not isinstance(value,list) or len(value)>20:reject(field,'必须是最多20项的字符串数组')
        for index,item in enumerate(value):require_text(item,field+'['+str(index)+']',500)
    if not isinstance(response,dict):reject('response','必须为JSON对象')
    if agent=='GoalDiagnosisAgent':
        require_text(response.get('summary'),'summary',2000);strings(response.get('risks'),'risks')
    elif agent=='LearningReplanAgent':
        require_text(response.get('reason'),'reason',2000);strings(response.get('recommendations'),'recommendations')
    elif agent=='PlanReviewAgent':
        if type(response.get('approved')) is not bool:reject('approved','必须是布尔值true或false，不能用字符串')
        strings(response.get('issues'),'issues')
        if 'suggestions' in response:strings(response['suggestions'],'suggestions')
        if response['approved'] and response['issues']:reject('issues','approved=true时必须为空数组')
        if not response['approved'] and not response['issues']:reject('issues','approved=false时必须说明具体问题')
    elif agent=='PathBuildingAgent':
        require_text(response.get('reason'),'reason',2000);tasks=response.get('tasks')
        if not isinstance(tasks,list) or len(tasks)>30:reject('tasks','必须是最多30项的数组')
        for index,task in enumerate(tasks):
            prefix='tasks['+str(index)+']'
            if not isinstance(task,dict):reject(prefix,'必须为对象')
            require_text(task.get('skill_id'),prefix+'.skill_id',100)
            if 'title' in task:require_text(task['title'],prefix+'.title',200)
            require_text(task.get('instructions'),prefix+'.instructions',4000)
            if type(task.get('minutes')) is not int or not 1<=task['minutes']<=1440:reject(prefix+'.minutes','必须是1至1440的整数')
            refs=task.get('citation_version_ids')
            if not isinstance(refs,list) or not 0<=len(refs)<=8 or not all(text(x,100) for x in refs):reject(prefix+'.citation_version_ids','必须含0至8个非空版本ID字符串；无资源时为空，每项最多100字')
            if len(set(refs))!=len(refs):reject(prefix+'.citation_version_ids','不能重复')
    else:reject('agent','不支持该智能体')
    return response
