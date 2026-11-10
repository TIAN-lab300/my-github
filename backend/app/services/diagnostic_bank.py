"""A distinct, curated equivalent test; never shuffle disclosed answers as new evidence."""
RETEST=[
 {'id':'r1','skill':'functions','prompt':'def add(a,b): return a+b 中 a、b 是什么？','options':['形参','输出内容','函数名'],'answer':'0','explanation':'定义中接收调用值的名字称为形参。'},
 {'id':'r2','skill':'functions','prompt':'函数执行到return后会怎样？','options':['从头重来','退出本次调用并返回值','继续全部后续语句'],'answer':'1','explanation':'return结束本次函数调用。'},
 {'id':'r3','skill':'recursion','prompt':'递归求和在n=0时直接返回0，这属于什么？','options':['递归展开','语法错误','基本情况'],'answer':'2','explanation':'基本情况不再递归调用。'},
 {'id':'r4','skill':'recursion','prompt':'sum(n)=n+sum(n-1)，当n趋向0时为何能结束？','options':['规模趋向基本情况','使用了全局变量','每次创建了循环'],'answer':'0','explanation':'规模递减并最终命中结束条件。'},
 {'id':'r5','skill':'stack','prompt':'递归展开时每层局部变量通常保存在哪里？','options':['同一个全局位置','各自的调用栈帧','源代码文件'],'answer':'1','explanation':'不同调用具有各自栈帧。'},
 {'id':'r6','skill':'stack','prompt':'两次函数调用完成后，哪个栈帧先移除？','options':['更早创建的','随机选择','更晚创建且先返回的'],'answer':'2','explanation':'调用栈按后进先出返回。'}]

def validate_answers(questions,answers,partial=False):
    from app.core.security import fail
    by_id={q['id']:q for q in questions}
    if not isinstance(answers,dict) or set(answers)-set(by_id): fail(422,'答案包含无效题目编号')
    if not partial and set(answers)!=set(by_id): fail(422,'请完成全部诊断题')
    for id,value in answers.items():
        q=by_id[id]
        if not isinstance(value,str) or value not in {str(i) for i in range(len(q.get('options',[])))}: fail(422,'请选择有效选项')
