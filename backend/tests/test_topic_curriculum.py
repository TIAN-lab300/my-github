from datetime import date,timedelta
from test_platform import classroom,P


def topic():
    node={'id':'lists','name':'列表','aliases':['list'],'minutes':20}
    for phase,prompt in [('diagnostic','列表保存的元素怎样排列？'),('retest','列表元素是否具有顺序？'),('practice','列表中的第一个元素下标是多少？')]:
        node[phase+'_questions']=[{'id':phase+'-lists','skill':'lists','prompt':prompt,'options':['有序或下标0','无序或下标1'],'answer':'0','explanation':'列表为有序序列，起始下标为0。'}]
    return {'nodes':[node],'edges':[]}


def test_reviewed_new_topic_end_to_end(clients):
    admin=clients['admin'];teacher=clients['teacher'];student=clients['student']
    body=topic();graph=admin.post(P+'/admin/graphs',json=body).json()['id']
    assert admin.post(P+'/admin/graphs/'+graph+'/activate').status_code==200
    curriculum=student.get(P+'/curriculum/skills').json()
    assert curriculum['skills'][0]['id']=='lists' and 'answer' not in str(curriculum)
    cid,_=classroom(clients)
    resource=teacher.post(P+'/resources',data={'description':'课程','tags':'列表','source_license':'自编','class_id':cid},files=[('files',('lists.txt','列表是有序序列，元素下标从0开始。'.encode(),'text/plain'))]).json()[0]['id']
    teacher.post(P+'/resources/'+resource+'/publish')
    goal=student.post(P+'/goals',json={'title':'学习列表','weekly_minutes':120,'due_date':(date.today()+timedelta(days=10)).isoformat(),'class_id':cid}).json()['id']
    sheet=student.post(P+'/goals/'+goal+'/diagnoses').json()
    assert sheet['questions'][0]['skill']=='lists'
    student.post(P+'/diagnoses/'+sheet['id']+'/submit',json={'answers':{sheet['questions'][0]['id']:'1'},'minutes':2})
    run=student.post(P+'/goals/'+goal+'/planning-runs',headers={'Idempotency-Key':'new-topic'}).json()['run_id']
    completed=student.get(P+'/runs/'+run).json()
    assert completed['status']=='succeeded',completed
    path=student.get(P+'/paths/'+completed['result_id']).json()
    assert 'diagnostic_questions' not in str(path['validation']['graph'])
    assert student.post(P+'/paths/'+path['id']+'/accept').status_code==200
    item=path['tasks'][0]['id']
    practice=student.get(P+f'/paths/{path["id"]}/items/{item}/assessment').json()
    assert practice['questions'][0]['id']=='practice-lists'
    attempt=student.post(P+f'/paths/{path["id"]}/items/{item}/attempts',json={'answers':{'practice-lists':'0'},'minutes':3})
    assert attempt.status_code==200 and attempt.json()['score']==1


def test_incomplete_new_topic_cannot_activate(clients):
    admin=clients['admin']
    graph=admin.post(P+'/admin/graphs',json={'nodes':[{'id':'unknown','minutes':10}],'edges':[]}).json()['id']
    assert admin.post(P+'/admin/graphs/'+graph+'/activate').status_code==422
