"""Short Chinese question/answer summaries, each traceable to a read official answer."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs'/'curriculum'

def main():
    courses=json.loads((OUT/'bit-cs-all-years-draft.json').read_text(encoding='utf-8'))['courses']
    catalog=json.loads((OUT/'question-answer-sources.json').read_text(encoding='utf-8'))
    packs={p['id']:p for p in catalog['packs']}
    # Locator and summaries do not reproduce full worksheets or their code/figures.
    raw=[
      ('algorithms-basic-01','C03','队列','Problem 1-2(a)','用原题给定的双端操作交换序列首尾元素。','依次取出首尾，再按相反位置插回，常数次操作，时间O(1)。',False),
      ('algorithms-basic-01','C03','队列','Problem 1-2(b)','将前k个元素按顺序移至末尾。','重复k次取出首元素并插到末尾，时间O(k)。',False),
      ('algorithms-basic-02','C14','递归与递推','Problem 1-1(a)','在原题基本情况假设下，求T(n)=2T(n/2)+O(√n)的紧确阶。','Θ(n)；叶子数量提供线性下界，递归树各层合计为线性上界。',False),
      ('algorithms-basic-02','C14','递归与递推','Problem 1-1(c)','原题单调性条件下，求T(n)=T(n/3)+T(n/4)+Θ(n)的阶。','Θ(n)；用2T(n/3)+Θ(n)给出上界，再利用线性非递归工作给下界。',False),
      ('assembly-01','C07','指令集与寄存器','ASM-1B','原题ASM-1代码若正常返回，返回值是什么？','返回1；返回前写入返回值寄存器的是常数1。',True),
      ('assembly-01','C07','条件码与分支','ASM-1D','原题改用无符号比较时，哪个条件跳转须调整？','有符号小于跳转jl改为无符号小于跳转jb；其他指令须结合原题语义判断。',True),
      ('assembly-01','C07','汇编与高级语言对应','ASM-2A','把原题汇编对全局无符号变量a、b的操作概括为C表达式。','a -= (b & 255)。应结合原题声明及目标架构核对。',True),
      ('cpp-01','C06','C++类型与引用','Question #1','初始化与赋值有何区别？可各发生几次？','初始化发生于对象创建时且一次；随后可多次赋值。',False),
      ('cpp-01','C06','C++类型与引用','Question #2','未定义行为意味着什么？','程序执行了C++标准未规定结果的操作，结果无保证，不能以某次正常运行为正确性证明。',False),
      ('cpp-01','C06','C++类型与引用','Question #3','读入两个整数，输出两者之和与差；原题样例输入6、4。','样例结果分别为10和2；参考实现采用整数输入和加减运算。',False),
      ('rl-01','C22','时序差分','Week2 Q1(a)','在原题随机逼近假设下，步长α_n=1/n是否满足两项步长条件？','满足：步长级数发散，平方步长级数收敛。并非脱离原题假设保证任意强化学习算法收敛。',True),
      ('rl-01','C22','时序差分','Week2 Q1(b)','原题中常数步长α_n=1/2是否满足收敛所需的两项条件？','不满足平方步长和有限的条件，因此不能据此保证收敛。',True),
      ('rl-01','C22','时序差分','Week2 Q1(c)','原题中α_n=1/n³是否同时满足两项条件？','否；步长之和有限，第一项条件不成立。',True),
      ('distributed-2024-1','C27','批处理','Exam1 Q1，题目印刷第2页／答案第3页','根据原题MapReduce性能图，首次调用应用Reduce函数大约是什么时候？','官方选择约150秒；需等待全部Map结束。图形与上下文是题目的一部分。',True),
      ('nlp-01','C23','词向量','2018 Midterm Q1(a)，印刷第2页','原题Skip-gram选项中，最终词向量采用哪种合成方式？','官方勾选输入、输出词向量的平均或相加；仅作该课程原题答案记录，不视为唯一通用实现。',True),
    ]
    drafts=[]
    for i,(pack_id,cid,topic,locator,q,a,requires_original) in enumerate(raw,1):
        c=next(c for c in courses if c['id']==cid)
        skill=next((s for s in c['skills'] if s['name']==topic),None)
        assert skill,(cid,topic)
        pack=packs[pack_id]
        drafts.append(dict(id=f'QA-DRAFT-{i:03d}',course_id=cid,course_name=c['name'],candidate_skill_id=skill['id'],
            knowledge_point=topic,pack_id=pack_id,original_locator=locator,
            question_zh_summary=q,official_answer_zh_summary=a,
            question_url=pack['question_url'],answer_url=pack['solution_url'],
            translation_kind='short_paraphrase_not_full_translation',requires_original_context=requires_original,
            status='pending_teacher_review',license_review='pending',published=False,approved_for_scoring=False,
            use='公开练习候选，不是保密重测试题'))
    artifact=dict(scope='官方题目及答案的简短中文摘要，保留原题定位',items=drafts,
        excluded_items=[{'pack_id':'distributed-2024-1','locator':'Q2','reason':'官方题解明确指出题目有误，不建立有效评分项。'}],
        student_bank_imported=False)
    (OUT/'question-review-drafts.json').write_text(json.dumps(artifact,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    verified={'pdf_pair_read','same_document_answers_read'}
    n=sum(p['status'] in verified for p in packs.values())
    md=['# 公开试题与答案核查清单','',
        f"本轮共收集{len(packs)}个题组来源候选，其中{n}个已读取PDF或同页题解，另有{len(packs)-n}个附件待核实；不是{len(packs)}道试题。另整理{len(drafts)}条有原题定位的中文题答摘要。",'',
        '资料均为待审核候选；原题图形、代码、假设及分题结构不可在转换时丢弃。未发布到学生诊断库。','',
        '## 题目与答案成对链接','','|编号／题组|适用课程|题目|答案|核查状态|','|---|---|---|---|---|']
    names={c['id']:c['name'] for c in courses}
    statuses={'pdf_pair_read':'PDF可读；逐题审核未完成','same_document_answers_read':'网页题目和题解已读','attachments_unverified':'仅索引配对；附件不可确认','year_mismatch_pending_review':'题目答案年份冲突'}
    for p in packs.values():
        md.append(f"|{p['id']} · {p['label']}|{'、'.join(names[c] for c in p['course_ids'])}|[原题]({p['question_url']})|[参考答案]({p['solution_url']})|{statuses.get(p['status'],p['status'])}|")
    md+=['','## 中文题答摘要','','简短摘述供审核，完整题目以对应来源为准，不能直接用摘要代替试卷。']
    for d in drafts:
        md+=['',f"### {d['id']} · {d['course_name']} · {d['knowledge_point']}",'',
            f"原题定位：{d['original_locator']}。",'',
            '题意：'+d['question_zh_summary'],'',
            '官方答案要点：'+d['official_answer_zh_summary'],'',
            f"[题目来源]({d['question_url']}) · [答案来源]({d['answer_url']})",'',
            '状态：待教师及许可审核；'+('必须结合原题代码、图或假设。' if d['requires_original_context'] else '入库前仍须补全题目条件与评分规则。')]
    md+=['','## 全部36门课程的覆盖与缺口','','|课程|本轮已读取题答来源|情况|','|---|---|---|']
    for c in courses:
        ready=[p['id'] for p in packs.values() if c['id'] in p['course_ids'] and p['status'] in verified]
        candidate=[p['id'] for p in packs.values() if c['id'] in p['course_ids']]
        note='仅候选课程级关联，尚未核对全部知识点' if ready else '索引有配对，附件受限，尚未取得可靠题答' if candidate else '项目需评分量规，无统一标准答案' if c['assessment_mode']=='project_rubric' else '本轮尚未取得可核实的官方题答配对'
        md.append(f"|{c['name']}|{'、'.join(ready) or '无'}|{note}|")
    md+=['','## 排除及待核实','',
        '- Stanford CS143当前WA1题目与答案封面年份不一致，不能只因链接写着Solutions就当成准确配对。',
        '- MIT分布式系统2024 Exam1 Q2，官方题解明确指出问题本身有误，已排除评分用途。',
        '- 数据库Google Drive附件访问失败；安全试卷附件返回跳转页；组成课程部分附件跳转学校认证。均不绕过访问限制。',
        '- 开放索引不保证每份附件都可重用。MIT OCW非商业署名相同方式共享及第三方材料例外需逐件核对；其他网站未确认许可前保持外链。',
        '- 公开试卷可用于练习，不能不加处理地充当尚未公开的等价重测试卷；同一题目跨课程引用不重复计数。', '',
        '配对校验、PDF页数、哈希及附件访问状态见[结构化记录](question-answer-sources.json)。中文摘要见[题目草稿数据](question-review-drafts.json)。']
    (OUT/'question-answer-sources.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
    print(json.dumps({'packs':len(packs),'readable_packs':n,'chinese_drafts':len(drafts),
        'courses_with_readable_candidates':len({c for p in packs.values() if p['status'] in verified for c in p['course_ids']}),'published_questions':0}))

if __name__=='__main__':main()
