"""Reviewed graph topic banks, with compatibility for the original curated curriculum."""
import json
from app.core.db import one
from app.core.security import fail
from app.services.learning import QUESTIONS,SKILLS
from app.services.diagnostic_bank import RETEST

PRACTICE={
    'functions':[{'id':'practice-functions','skill':'functions','prompt':'表达式 f(3) 中，3 通常表示什么？','options':['实参','函数名','返回语句'],'answer':'0','explanation':'调用时传入的值称为实参。'}],
    'recursion':[{'id':'practice-recursion','skill':'recursion','prompt':'factorial(n) 调用 factorial(n-1) 的主要作用是什么？','options':['增加问题规模','向基本情况缩小问题规模','清空调用栈'],'answer':'1','explanation':'规模逐步缩小，最终到达基本情况。'}],
    'stack':[{'id':'practice-stack','skill':'stack','prompt':'A调用B，B调用C；C结束后先返回哪里？','options':['程序入口','A的入口','B的调用位置'],'answer':'2','explanation':'调用栈后进先出，先返回最近调用者B。'}]}


def question_bank(db,phase,graph_id=None):
    graph=one(db,'SELECT * FROM graph_versions WHERE id=:id',id=graph_id) if graph_id else one(db,'SELECT * FROM graph_versions WHERE active=1')
    fallback=QUESTIONS if phase=='diagnostic' else RETEST if phase=='retest' else [question for bank in PRACTICE.values() for question in bank]
    if not graph:return fallback,'curated-v1'
    questions=[]
    for node in json.loads(graph['nodes']):
        questions.extend(node.get(phase+'_questions',[question for question in fallback if question['skill']==node['id']]))
    return questions,graph['id']


def validate_banks(nodes):
    identifiers=set();prompts=set()
    for node in nodes:
        for phase in ('diagnostic','retest','practice'):
            bank=node.get(phase+'_questions')
            if bank is None and node['id'] in {skill['id'] for skill in SKILLS}:continue
            if not isinstance(bank,list) or not 1<=len(bank)<=12:fail(422,'每个新主题须提供初测、等价重测和练习题各1至12道')
            for question in bank:
                if not isinstance(question,dict) or question.get('skill')!=node['id']:fail(422,'题目必须映射其所在知识点')
                key=question.get('id');prompt=question.get('prompt');options=question.get('options')
                if not isinstance(key,str) or not key or key in identifiers or not isinstance(prompt,str) or not prompt.strip() or prompt in prompts:fail(422,'初测、重测和练习题的编号及题干须非空且不重复')
                if not isinstance(options,list) or not 2<=len(options)<=8 or any(not isinstance(option,str) or not option.strip() for option in options):fail(422,'诊断选择题须有2至8个有效选项')
                if question.get('kind','single')!='single' or question.get('answer') not in {str(index) for index in range(len(options))} or not isinstance(question.get('explanation'),str) or not question['explanation'].strip():fail(422,'题目须有唯一正确选项与解析')
                identifiers.add(key);prompts.add(prompt)


def keywords(nodes):
    defaults={'functions':['函数','function','def '],'recursion':['递归','recursion'],'stack':['调用栈','栈','stack']}
    return {node['id']:defaults.get(node['id'],[node.get('name',node['id']),node['id']])+node.get('aliases',[]) for node in nodes}
