"""Public project-authored worked examples, never student submissions or source quotations."""
EXAMPLES={
 'expressions':{'text':'表达式先代入变量，再按括号和运算优先级求值。例：(3+x)*2-x，x=4时为10。','code':'x = 4\nresult = (3 + x) * 2 - x','prompt':'x=4时，(3+x)*2-x等于多少？','answer':'10','rubric':'先代入得(3+4)*2-4，再算7*2-4=10。','worked':'代入x=4，括号内3+4=7，乘2得14，再减4得10。'},
 'functions':{'text':'函数参数接收输入，return把值交给调用者。给定f(x)=2*x+1，有f(1)=3、f(2)=5、f(3)=7。若反推，必须明确限定仿射函数f(x)=a*x+b；只有两点不能唯一确定任意函数。','code':'def f(x):\n    return 2 * x + 1\nresult = f(3)','prompt':'已限定f(x)=a*x+b且f(1)=3、f(2)=5，求a、b及f(3)。','answer':'a=2，b=1，f(3)=7','rubric':'列a+b=3及2a+b=5，相减得a=2，再得b=1；代入3得7。不得泛化到未限定函数族。','worked':'按给定函数式计算f(3)=2*3+1=7。'},
 'recursion':{'text':'递归应有基本情况，递归步骤应使问题规模趋向该情况。以下total限定非负整数，n=0返回0，否则返回n+total(n-1)。total(2)返回3。','code':'def total(n):\n    if n == 0:\n        return 0\n    return n + total(n - 1)\nresult = total(2)','prompt':'对给定非负整数累加函数total，写出total(2)的参数展开、基本情况和最终返回值。','answer':'2→1→0；total(0)=0；total(1)=1；total(2)=3','rubric':'明确输入域n>=0、基本情况返回0、每次n减1，回收得到1和3。不是求阶乘。','worked':'total(2)=2+total(1)，total(1)=1+total(0)，依次返回0、1、3。'},
 'stack':{'text':'普通同步函数调用按后进先出返回。设main调用a，a调用b，b返回2，a返回b的结果加1，main接收3。完整追踪包含6个调用/返回事件和含初始空栈的7个快照；不能把抽样快照冒充全程。','code':'def b():\n    return 2\ndef a():\n    return b() + 1\ndef main():\n    return a()\nresult = main()','prompt':'限定从调用main前的空栈开始，到main返回后的空栈结束，列出给定代码每个调用/返回事件及事件后的栈。','answer':'[]→[main]→[main,a]→[main,a,b]→[main,a]→[main]→[]；结果3','rubric':'6个事件：call main、call a、call b、return b、return a、return main；加初始态共7个快照，栈顶在右。','worked':'进入main/a/b，再依次返回b/a/main；b返回2，a返回3，main返回3。','events':['call main','call a','call b','return b','return a','return main'],'states':[[],['main'],['main','a'],['main','a','b'],['main','a'],['main'],[]]}}



# Runtime beginner material is distinct from the affine-family evaluation scenario.
PLANNING_EXAMPLES={**EXAMPLES,'functions':{
 'text':'Python用def定义函数；调用时将实参绑定到形参，return将表达式的值返回给调用者。这里实参是整数，double将输入乘以2。',
 'code':'def double(x):\n    return x * 2\nanswer = double(3)',
 'prompt':'先执行函数定义，再调用double(3)。指出函数名、形参、实参，写出表达式x*2和answer的值。',
 'answer':'函数名double，形参x，实参3；x*2=6，answer=6。',
 'rubric':'区分定义与调用；调用时x绑定整数3，计算3*2得到6，由return返回，answer接收6。不要求方程组或函数族反推。',
 'worked':'定义阶段创建函数并绑定名字double，此时不执行函数体；随后调用double(3)，将x绑定3，求值3*2，返回6并赋给answer。',
 'scope':'Python初学函数定义、参数传递和返回值；不引入代数反推或栈快照。'}}


PLANNING_EXAMPLES['stack']={**EXAMPLES['stack'],'material_revision':'runtime-v3',
 'trace_semantics':'代码先按b、a、main的顺序定义函数，再执行main()；调用顺序是main→a→b，定义顺序不是调用顺序。states只记录栈帧，返回值单独记录。',
 'trace_rows':[
  {'event':'initial','frames':[],'return_value':None},
  {'event':'call main','frames':['main'],'return_value':None},
  {'event':'call a','frames':['main','a'],'return_value':None},
  {'event':'call b','frames':['main','a','b'],'return_value':None},
  {'event':'return b','frames':['main','a'],'return_value':2},
  {'event':'return a','frames':['main'],'return_value':3},
  {'event':'return main','frames':[],'return_value':3}],
 'prompt':'仅依据本项目给定worked_example.code，按序号0至6列出初始态及全部6个事件、事件后的栈帧；在return b/a/main行标注返回值2/3/3，调用行无返回值。',
 'rubric':'序号0为空栈；序号1至6分别对应6个events，states与栈帧列逐项一致；返回行分别标2、3、3，最终result=3。无须在调用行编造返回值。'}
