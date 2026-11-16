"""Build an explicit, reviewable original bank; never infer answers from live models."""
import hashlib,json,random
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/curriculum'
VERSION='original-foundations-2026-11-16-v1'
SOURCE='项目原创基础题，AI辅助编写与技术自检；允许本项目教学使用。不是北理工官方试题，未经过授课教师审核或难度标定。'

PROJECTS={
 'C17':[
 ('针对真实使用场景定义一个可验证的工程问题。','问题说明、目标用户、现状证据、成功指标','问题边界明确；证据可追溯；指标可检查'),
 ('编写需求规格并区分必须满足的约束与可协商目标。','需求清单、验收条件、资源及时间限制','需求可追踪；约束来源明确；验收条件可执行'),
 ('为关键技术选择比较至少两种可行方案。','方案对比、验证原型、选择理由与风险','比较维度一致；结论有证据；风险有应对措施'),
 ('制定团队分工与可跟踪的迭代计划。','任务负责人、依赖、里程碑、实际完成记录','责任清晰；依赖合理；偏差有解释和调整'),
 ('设计系统结构及关键模块接口。','架构图、接口契约、数据设计、关键决策记录','需求有对应设计；接口无歧义；约束有落实'),
 ('集成各模块并证明关键业务链路可运行。','版本化源码、构建步骤、集成演示和缺陷记录','可从干净环境构建；关键链路真实运行；失败能定位'),
 ('针对关键需求建立测试与质量证据。','测试设计、执行结果、缺陷及修复验证','断言来自需求；覆盖边界与权限；结果可复现'),
 ('部署系统并验证备份恢复与运行状态。','部署说明、配置清单、监控和恢复演练记录','可按步骤部署；秘密不泄露；恢复结果已验证'),
 ('分析项目的隐私安全与工程伦理风险。','资产数据清单、威胁分析、权限及责任安排','风险与场景对应；措施有验证；剩余风险说明明确'),
 ('汇报成果并复盘计划与实际结果差异。','演示、成果索引、个人贡献、局限与改进清单','成果可核对；贡献有记录；结论不夸大')],
 'C18':[
 ('提出范围明确且可以研究或验证的毕业设计问题。','选题背景、研究问题、目标与范围说明','问题明确；价值有依据；目标可以验证'),
 ('检索并比较与选题直接相关的研究或工程资料。','检索策略、文献表、比较综述与引用','来源可核对；比较有维度；区分原文结论与自身推断'),
 ('设计能够回答问题的研究或工程方案。','方案说明、替代方案、可行性及风险分析','方案与目标一致；依据充分；限制可解释'),
 ('提交开题材料并回应关键可行性问题。','开题报告、时间计划、评议与修改记录','目标清晰；计划可行；关键意见已有回应'),
 ('实现方案并设计可信的验证实验。','源码或原型、实验协议、基线与变量控制','实现可运行；比较公平；实验能够检验目标'),
 ('分析数据结果并讨论支持范围与不确定性。','原始数据、处理脚本、图表和结论','数据来源清楚；计算可复查；不把相关性夸大为因果'),
 ('提供可重现主要结果的材料。','环境依赖、版本、参数、随机种子与运行命令','步骤完整；关键结果可重跑；环境差异有说明'),
 ('核查引用授权数据使用与学术诚信。','引用核查、许可说明、贡献和工具使用声明','引用准确；授权合理；不存在捏造数据和隐瞒来源'),
 ('撰写结构完整并能追踪论证依据的论文。','论文、图表来源、术语与参考文献','结构清楚；论点有证据；格式符合实际学校要求'),
 ('完成答辩展示并归档成果。','答辩材料、问答记录、最终论文与源码索引','展示与实物一致；能解释局限；归档可定位可复查')]
}

def build():
    courses=json.loads((BASE/'bit-cs-all-years-draft.json').read_text(encoding='utf-8'))['courses']
    groups={};current=None
    for line in (BASE/'original-bank-claims.txt').read_text(encoding='utf-8').splitlines():
        if not line.strip() or line.startswith('#'):continue
        if line.startswith('['):
            current=line[1:-1]
            if current in groups:raise ValueError('Duplicate course group')
            groups[current]=[]
        else:
            if current is None:raise ValueError('Missing course group')
            groups[current].append(line)
    questions=[];rubrics=[];coverage=[]
    for course in courses:
        cid=course['id'];skills=course['skills']
        if cid in PROJECTS:
            assert len(PROJECTS[cid])==len(skills)
            for skill,(task,deliverables,criteria) in zip(skills,PROJECTS[cid],strict=True):
                rubrics.append({'id':VERSION+'-'+skill['id'],'course_id':'public-'+cid,'skill_id':'public-'+skill['id'],
                    'skill_name':skill['name'],'task':task,'deliverables':deliverables.split('、'),'criteria':criteria.split('；'),
                    'levels':{'0':'未提交有效证据','1':'已提交但关键条件缺失或无法核实','2':'全部检查项有有效证据，满足基础要求','3':'满足基础要求，另有独立复现或充分比较与局限分析'},
                    'max_score':3,'grading':'teacher_only','source':SOURCE})
            coverage.append({'course_id':'public-'+cid,'course_name':course['name'],'skills':len(skills),'mode':'project_rubric','rubrics':len(skills),'questions':0})
            continue
        assert len(groups[cid])==len(skills),(cid,'Skill/claim row mismatch')
        for skill,line in zip(skills,groups[cid],strict=True):
            assertions=line.split('|');assert len(assertions)==3
            # Deterministic mixing avoids the same true/false pattern for each phase.
            random.Random(VERSION+skill['id']).shuffle(assertions)
            for phase,assertion in zip(('diagnostic','practice','retest'),assertions,strict=True):
                statement,reason=assertion.split('=>');truth=not statement.startswith('!');statement=statement.removeprefix('!')
                ident=VERSION+'-'+skill['id']+'-'+phase
                options=['正确','错误'];random.Random(ident).shuffle(options)
                questions.append({'id':ident,'course_id':'public-'+cid,'course_name':course['name'],
                    'skill_id':'public-'+skill['id'],'skill_name':skill['name'],'phase':phase,
                    'kind':'binary_single_choice','level':'foundation',
                    'prompt':'关于“'+skill['name']+'”，判断以下说法是否正确：\n'+statement+'。',
                    'options':options,'answer':options.index('正确' if truth else '错误'),
                    'explanation':('该说法正确。' if truth else '该说法错误。')+reason+'。','source':SOURCE})
        coverage.append({'course_id':'public-'+cid,'course_name':course['name'],'skills':len(skills),'mode':'knowledge_test','questions':len(skills)*3,'per_skill_per_phase':1})
    assert set(groups)=={c['id'] for c in courses if c['id'] not in PROJECTS}
    assert len(questions)==1071 and len(rubrics)==20
    assert len({q['prompt'] for q in questions})==len(questions)
    assert all(len(q['options'])==2 and q['answer'] in (0,1) and q['explanation'] for q in questions)
    payload={'version':VERSION,'provenance':SOURCE,'review':'technical_self_review_not_teacher_approval',
        'limitations':['基础概念判断题，不是完整期末试卷','每知识点每用途仅1题，重测用尽后需扩充','三用途题目不是已标定的等难度平行卷','不含编程、证明、综合计算的自动评分','既有知识点仍需对照正式教学大纲核实'],
        'coverage':coverage,'questions':questions,'project_rubrics':rubrics}
    target=BASE/'original-foundations-bank.json';target.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lines=['# 原创基础题库覆盖记录','','题目为项目自编基础判断题，不是北理工官方试卷。AI辅助编写与技术自检，授课教师尚未审核，未标定难度。',
        '','34门理论课程、357个知识点，每点初测/练习/重测各1题，共1071题；两门项目课程20项任务量规。',
        '','|课程|知识点|初测|练习|重测|项目量规|','|---|---:|---:|---:|---:|---:|']
    for c in coverage:
        n=c['skills'] if c['mode']=='knowledge_test' else 0
        lines.append(f"|{c['course_name']}|{c['skills']}|{n}|{n}|{n}|{c.get('rubrics',0)}|")
    lines+=['','每知识点每用途仅1题；重测已见题不复用。增加每点题数前必须扩充相应用途的题目。基础判断不能代替编程、证明、综合设计与最终课程验收。',
        '','题目、答案和解释见 original-foundations-bank.json；逐条断言与纠错依据见 original-bank-claims.txt。']
    (BASE/'original-bank-coverage.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'questions':len(questions),'rubrics':len(rubrics),'courses':len(coverage),'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}))

if __name__=='__main__':build()
