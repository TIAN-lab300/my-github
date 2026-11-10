from datetime import datetime,timedelta,timezone
from test_platform import classroom,P


def test_code_task_grading_and_retry_boundary(clients,monkeypatch):
    from app.services import code_judge
    cid,_=classroom(clients);teacher=clients['teacher'];student=clients['student']
    payload={'class_id':cid,'title':'两数相加','description':'读取两个整数并输出和','due_at':(datetime.now(timezone.utc)+timedelta(days=3)).isoformat(),'minutes':20,'mode':'code','code_cases':[{'stdin':'1 2','stdout':'3'},{'stdin':'0 0','stdout':'0'}]}
    created=teacher.post(P+'/teacher/tasks',json=payload)
    assert created.status_code==201,created.text
    task_id=created.json()['id']
    assert teacher.post(P+'/teacher/tasks/'+task_id+'/publish').status_code==200
    task=next(item for item in student.get(P+'/learners/me/tasks').json() if item['id']==task_id)
    assert not task['code_cases']
    monkeypatch.setattr(code_judge.shutil,'which',lambda binary:None)
    submit=P+'/tasks/'+task_id+'/attempts'
    assert student.post(submit,json={'text':'print(3)','minutes':4}).status_code==503
    calls=[]
    monkeypatch.setattr(code_judge,'execute_case',lambda code,case:calls.append(case) or {'passed':case['stdout']=='3','status':'ok'})
    result=student.post(submit,json={'text':'print(3)','minutes':4})
    assert result.status_code==200 and result.json()['score']==.5
    assert student.post(submit,json={'text':'print(0)','minutes':4}).json()['id']==result.json()['id']
    assert len(calls)==2
    assert clients['student2'].post(submit,json={'text':'print(3)','minutes':4}).status_code==404


def test_docker_command_has_isolation_limits(monkeypatch):
    from io import BytesIO
    from app.services import code_judge
    commands=[]
    class Input(BytesIO):
        def close(self):pass
    class Process:
        returncode=0
        stdin=Input();stdout=BytesIO(b'3\n')
        def poll(self):return 0
        def wait(self,timeout=None):return 0
    monkeypatch.setattr(code_judge.shutil,'which',lambda binary:'docker')
    monkeypatch.setattr(code_judge.subprocess,'Popen',lambda command,**options:commands.append(command) or Process())
    monkeypatch.setattr(code_judge.subprocess,'run',lambda *args,**kwargs:None)
    result=code_judge.execute_case('print(3)',{'stdin':'','stdout':'3'})
    assert result['passed']
    command=commands[0]
    assert '--read-only' in command and command[command.index('--network')+1]=='none'
    assert command[command.index('--memory')+1]=='128m'
    assert command[command.index('--user')+1]=='65534:65534'
    assert '--pull=never' in command and '--pids-limit' in command and '-v' not in command
