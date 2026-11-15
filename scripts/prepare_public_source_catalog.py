"""Persist manually browsed primary-source links; does not import or copy questions."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs' / 'curriculum'
CHECKED = '2026-11-14'
# Each entry was opened or returned by an official-site search in this session.
RAW = '''
S01|北理工C语言程序设计（上）|https://www.icourse163.org/course/BIT-20019|zh|课程目录|条件分支、循环、C语言基础|视频和测验可能需报名登录，不据此覆盖完整C语言课程
S02|CS50公开练习|https://cs50.harvard.edu/x/practice/|en|练习题|C语言与编程练习|运行检查工具和提交可能需环境及账号；没有本地题目转换
S03|MIT 6.006算法课程|https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/|en|讲义与课程|数据结构、算法|课程目录与题库可互相定位
S04|MIT 6.006练习页|https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/pages/practice-problems/|en|练习题|数据结构与算法练习|仅核对索引，未逐题审核答案或难度
S05|MIT 6.042J计算机数学|https://ocw.mit.edu/courses/6-042j-mathematics-for-computer-science-spring-2015/|en|开放教材|逻辑、证明、离散数学|组合数学的专门深度内容仍需补充
S06|Nand to Tetris项目|https://www.nand2tetris.org/course|en|实验项目|逻辑门、计算机硬件、汇编器、编译器|使用Hack教学架构；不能直接当作x86或本校数字电路实验
S07|LearnCpp作者教程|https://www.learncpp.com/|en|教程|C++类、继承、模板、资源管理|作者教程，转载许可待核对，优先外链
S08|Harvard CS61系统课程|https://cs61.seas.harvard.edu/site/2026/|en|课程与实验|机器表示、汇编、内存、并发|学期资源可能调整
S09|Harvard CS61汇编练习|https://cs61.seas.harvard.edu/site/2026/AsmEx/|en|练习题|汇编阅读与分析|需逐题确认指令集及语法，不混用RISC-V和x86
S10|CMU数据库课程作业|https://15445.courses.cs.cmu.edu/spring2026/assignments.html|en|作业索引|数据库系统|数据库内核项目偏进阶；ER建模与设计需补齐
S11|Berkeley CS186数据库|https://cs186berkeley.net/|en|讲义与练习索引|SQL、关系数据库|部分链接在Google Drive或教学平台，索引公开不等于所有附件可访问
S12|Berkeley CS61C组成与架构|https://cs61c.org/fa26/|en|课程与实验索引|机器结构、体系结构基础|部分作业在需登录平台；高级体系结构覆盖不足
S13|xv6教学操作系统教材|https://pdos.csail.mit.edu/6.1810/2024/xv6/book-riscv-rev4.pdf|en|教材与章节练习|进程、页表、陷阱、同步、文件系统|RISC-V教学系统，不等同所有操作系统内容
S14|Kurose与Ross网络实验|https://gaia.cs.umass.edu/kurose_ross/wireshark.php|en|网络实验|协议分析|需安装Wireshark，附属文件许可需逐项核对
S15|Kurose与Ross网络交互题|https://gaia.cs.umass.edu/kurose_ross/interactive/|en|交互练习|网络协议与计算|外部交互不能直接当作系统已具备自动评分
S16|Stanford CS143编译原理|https://web.stanford.edu/class/cs143/|en|讲义与试题索引|编译阶段、分析与实现|公开作业及部分答案索引；考试与编程提交另有平台
S17|MIT 6.045J计算理论|https://ocw.mit.edu/courses/6-045j-automata-computability-and-complexity-spring-2011/|en|讲义与作业|自动机、可计算性、复杂性|与算法分析课程共同覆盖复合课程
S18|MIT 6.046J算法设计|https://ocw.mit.edu/courses/6-046j-design-and-analysis-of-algorithms-spring-2015/|en|讲义与课程|算法设计与分析|不单独代表北理工完整教学大纲
S19|MIT 6.046J作业|https://ocw.mit.edu/courses/6-046j-design-and-analysis-of-algorithms-spring-2015/pages/assignments/|en|练习题|算法证明与设计|未逐题转换成单选题
S20|Sommerville软件工程作者资源|https://software-engineering-book.com/|en|课件与案例|软件工程方法|作者配套材料不表示整本教材可复制
S21|MIT Missing Semester|https://missing.csail.mit.edu/|en|工具课程|开发工具与工程实践|工具实践补充，不能替代完整程序设计方法课程
S22|MIT系统工程课程|https://ocw.mit.edu/courses/6-033-computer-system-engineering-spring-2018/|en|设计作业与案例|系统设计、工程分析|综合训练的参考任务，不是本校评分量规
S23|北理工2024—2025毕业设计工作通知|https://jwb.bit.edu.cn/tzgg/1642213a6d004d81b8c40ab0c1e4cfce.htm|zh|管理通知|毕业设计流程|仅该年度通知；具体专业要求、模板、评分仍需最新校内资料
S24|Berkeley CS188 AI存档|https://inst.eecs.berkeley.edu/~cs188/archive/fa24/|en|课程与项目|搜索、推理、人工智能|部分作业需平台；不认定与人工智能与计算科学A完全相同
S25|Stanford CS231n|https://cs231n.stanford.edu/|en|课程与作业索引|深度学习与计算机视觉|经典模式识别部分需补充
S26|动手学深度学习|https://d2l.ai/|en/zh|开放在线教材|神经网络、优化、注意力|中文入口由官网提供；仅核对目录，练习未逐题审核
S27|Spinning Up强化学习|https://spinningup.openai.com/en/latest/|en|算法教程与实现|策略与价值方法|依赖版本可能较旧，不直接承诺代码可运行
S28|Stanford CS224N|https://web.stanford.edu/class/cs224n/|en|课程与作业索引|自然语言处理|深度学习导向，基础语言学部分需补充
S29|Berkeley CS161安全教材|https://textbook.cs161.org/|en|在线教材|密码、Web与网络安全|用于课程概念；不能等同安全测试已获授权
S30|Boneh与Shoup密码学教材|https://crypto.stanford.edu/~dabo/cryptobook/|en|教材|对称密码、公钥、协议|研究生难度，需筛选本科适用内容
S31|MIT分布式系统历年考试|https://pdos.csail.mit.edu/6.824/quizzes.html|en|试题与答案索引|分布式系统|历年题公开，不能作为未公开重测题直接复用
S32|Apache Spark官方文档|https://spark.apache.org/docs/latest/|en|工具文档|批处理、流处理、分布式数据|动态版本入口；云服务模型与虚拟化仍需补齐
S33|Berkeley CS184图形学存档|https://cs184.eecs.berkeley.edu/|en|课程存档入口|计算机图形学|需进一步选定学期和具体作业附件
S34|FFmpeg官方文档|https://ffmpeg.org/documentation.html|en|工具文档|音视频处理|仅实践补充，不能代替多媒体编码理论
S35|Stanford CS147人机交互|https://hci.stanford.edu/courses/cs147/2026/au/|en|设计课程与项目|用户研究、原型、评价|需结合教师标准设计本地评价量规
S36|Lee与Seshia嵌入式系统|https://ptolemy.berkeley.edu/books/leeseshia/|en|教材与课程入口|嵌入式与信息物理系统|偏建模分析，设备驱动及目标板实验另补
S37|Stanford CS149并行计算|https://gfxcourses.stanford.edu/cs149/fall25/|en|课程与阅读|并行硬件与编程|部分功能需登录，不保证每个项目附件可取
S38|Chipyard官方文档|https://chipyard.readthedocs.io/en/stable/|en|工具与设计文档|SoC集成、仿真与生成器|进阶工具，RTL入门及评分题还需补充
S39|Software Foundations作者教材|https://softwarefoundations.cis.upenn.edu/|en|教材与形式化练习|逻辑、程序证明、语义|练习使用Rocq工具，不直接映射为客观题
S40|Tim Roughgarden算法博弈论|https://timroughgarden.org/f13/f13.html|en|讲义与练习|拍卖、机制、均衡|需核实数学先修与本科难度
'''

MAP = {
 'C01':['S01','S02'], 'C02':['S24','S02'], 'C03':['S03','S04'],
 'C04':['S05'], 'C05':['S06'], 'C06':['S07'], 'C07':['S08','S09'],
 'C08':['S11','S10'], 'C09':['S12','S06'], 'C10':['S13'],
 'C11':['S14','S15'], 'C12':['S16','S06'], 'C13':['S12','S37'],
 'C14':['S17','S18','S19'], 'C15':['S20'], 'C16':['S21','S08'],
 'C17':['S22','S20'], 'C18':['S23'], 'C19':['S24'], 'C20':['S25'],
 'C21':['S26','S25'], 'C22':['S27'], 'C23':['S28'], 'C24':['S29'],
 'C25':['S30','S29'], 'C26':['S31','S22'], 'C27':['S32','S31'],
 'C28':['S33'], 'C29':['S34'], 'C30':['S35'], 'C31':['S36'],
 'C32':['S37'], 'C33':['S38','S06'], 'C34':['S39'], 'C35':['S05'],
 'C36':['S40'],
}

def main():
    data=json.loads((OUT/'bit-cs-all-years-draft.json').read_text(encoding='utf-8'))
    sources=[]
    for line in RAW.strip().splitlines():
        ident,title,url,language,kind,topics,limits=line.split('|')
        sources.append(dict(id=ident,title=title,url=url,language=language,kind=kind,
            candidate_topics=topics,limitations=limits,verification='page_or_index_read',
            checked_on=CHECKED,imported=False,redistribution='link_only_pending_asset_review',
            question_items_extracted=0,answer_reviewed=False,cloud_processing_allowed=False))
    ids={s['id'] for s in sources}
    assert len(ids)==len(sources)==40
    assert set(MAP)=={c['id'] for c in data['courses']}
    assert all(set(v)<=ids for v in MAP.values())
    by_id={s['id']:s for s in sources}
    mappings=[]
    for c in data['courses']:
        c['public_source_candidates']=MAP[c['id']]
        c['source_mapping_status']='course_level_candidates_not_skill_verified'
        mappings.append(dict(course_id=c['id'],course_name=c['name'],source_ids=MAP[c['id']],
            coverage='partial_candidate',skill_level_verified=False,question_bank_ready=False,
            gaps=[by_id[s]['limitations'] for s in MAP[c['id']]]))
    manifest=dict(schema_version='source-catalog-1',checked_on=CHECKED,
        scope='用户提供的36门课程；公开来源候选，不是北理工官方题库',
        sources=sources,course_mappings=mappings,
        counts=dict(courses=36,source_entries=40,verified_skill_mappings=0,extracted_questions=0),
        license_references=[
            {'url':'https://ocw.mit.edu/pages/privacy-and-terms-of-use/','note':'MIT OCW内容通常按CC BY-NC-SA 4.0，第三方材料及另行标注内容需逐件检查。'},
            {'url':'https://cs50.harvard.edu/x/license/','note':'CS50页面标注CC BY-NC-SA 4.0；代码及第三方资源按各自许可核对。'}],
        failed_candidates=[
            'https://www.cs.cmu.edu/~15213/',
            'https://cryptobook.us/',
            'https://pdos.csail.mit.edu/6.824/2024/',
            'https://pdos.csail.mit.edu/6.5840/2024/',
            'https://web.stanford.edu/class/cs149/',
            'https://web.stanford.edu/class/cs147/',
            'https://chisel-bootcamp.readthedocs.io/en/latest/'],
        failed_note='抓取失败或目录内容不足，不等同网站永久失效；上述链接不作为已确认教学材料。')
    (OUT/'public-sources-catalog.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (OUT/'bit-cs-all-years-draft.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    md=['# 36门计算机专业课公开资料清单', '', f'核查日期：{CHECKED}。共40个公开来源条目、36门课程候选映射。', '',
        '本轮交付是可追溯的资料目录：已读取目标页或索引，未批量复制题目、附件或答案，未导入运行数据库。课程映射为人工初筛，不表示377个知识点全部覆盖。', '',
        '## 逐课程入口', '', '|课程|公开来源|获取后还需处理|','|---|---|---|']
    for c,m in zip(data['courses'],mappings):
        links='；'.join(f"[{s} {by_id[s]['title']}]({by_id[s]['url']})" for s in m['source_ids'])
        md.append(f"|{c['id']} {c['name']}|{links}|{'；'.join(m['gaps'])}|")
    md+=['','## 来源记录','','各条仅记录概述和用途；逐附件许可、题目质量、语言适配和目标架构仍待核对。']
    for s in sources:
        md+=['',f"### {s['id']} {s['title']}",'',f"[官方或作者页面]({s['url']})",'',
            f"- 类型：{s['kind']}；语言：{s['language']}。",
            f"- 候选范围：{s['candidate_topics']}。",
            f"- 限制：{s['limitations']}。",
            '- 核查程度：目标页或索引已读取；附件和题目未逐项验收。默认只保存外链，云端处理未授权。']
    md+=['','## 题库落地顺序','',
        '1. 优先处理C语言S01/S02、数据结构S03/S04、汇编S08/S09、网络S14/S15、编译S16、算法S19及分布式S31；这些已找到公开练习或试题索引。',
        '2. 逐题登记来源页、原题标识、知识点、题型、答案、解析、难度与使用条件；无答案或无法核实的题保留草稿。公开原题不直接作为未公开等价重测题。',
        '3. 中文转换及改编保留原始来源与许可说明，人工检查选项、语言标准、数值边界和答案。代码练习需补测例和执行环境；论述、证明、设计题不能自动当作单选评分。',
        '4. 按知识点检查初测、重测、练习覆盖，教师复核后才发布；题库不足按课程报告缺口。',
        '5. 毕设及综合训练改为成果与量规；官方通知仅支持流程设计，不能凭通知臆造学校评分标准。', '',
        '## 当前缺口','',
        '人工智能与计算科学A的校本内容、专门体系结构深度、组合数学高级内容、云计算基础理论、多媒体理论、SoC入门仍需补充。资料以英文为主，尚未完成中文教学适配。', '',
        '没有单门课程被标记为题库就绪。40条来源不是40个已安装课程库，也不是已入库的题目数量。','',
        '## 许可核查入口','']
    for item in manifest['license_references']:
        md.append(f"- [{item['url']}]({item['url']})：{item['note']}")
    md+=['','未明确开放许可的课程、书籍、工具文档仅链接；授权检查后再决定下载、改编、共享或发送模型。']
    (OUT/'public-sources-catalog.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
    for doc in (ROOT/'docx').glob('*.md'):
        with doc.open('a',encoding='utf-8') as f:
            f.write('\n\n## 2026-11-14 公开教学来源采集记录\n\n已为用户指定的36门课程整理40个公开来源条目，包含课程讲义、教材、练习/试题索引、工具文档及项目管理通知。详见[公开资料清单](../docs/curriculum/public-sources-catalog.md)与[来源元数据](../docs/curriculum/public-sources-catalog.json)。已核查目标页或索引，但逐知识点映射、题目提取、答案审核、授权导入均未完成；候选来源不能用于把课程或题库标为已验收。\n')
    print(json.dumps(manifest['counts']))

if __name__=='__main__':
    main()
