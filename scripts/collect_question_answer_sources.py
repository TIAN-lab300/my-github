"""Find public question/solution document pairs; preserve links, not exam full text."""
import concurrent.futures,hashlib,io,json,re,sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin,urlsplit
import httpx
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs'/'curriculum'
FAMILIES=[
 ('algorithms-basic','MIT 6.006 数据结构练习',['C03','C14'],'https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/pages/practice-problems/'),
 ('algorithms-advanced','MIT 6.046J 算法作业',['C14'],'https://ocw.mit.edu/courses/6-046j-design-and-analysis-of-algorithms-spring-2015/pages/assignments/'),
 ('discrete','MIT 6.042J 离散数学考试',['C04','C35'],'https://ocw.mit.edu/courses/6-042j-mathematics-for-computer-science-fall-2010/pages/exams/'),
 ('digital','MIT 6.004 数字与计算机结构考试',['C05','C09','C13'],'https://ocw.mit.edu/courses/6-004-computation-structures-spring-2009/pages/exams/'),
 ('software','MIT 6.102 软件构造考试',['C15','C16'],'https://web.mit.edu/6.102/www/sp26/exams/archive/'),
 ('ai','Berkeley CS188 人工智能考试',['C02','C19','C22'],'https://people.eecs.berkeley.edu/~russell/classes/cs188/f14/exams.html'),
 ('database','Berkeley CS186 数据库考试',['C08'],'https://cs186berkeley.net/sp24/resources/'),
 ('security','Berkeley CS161 安全考试',['C24','C25'],'https://fa24.cs161.org/resources/'),
]

class Tables(HTMLParser):
    def __init__(self):
        super().__init__();self.rows=[];self.row=None;self.anchor=None
    def handle_starttag(self,tag,attrs):
        if tag=='tr':self.row={'text':[],'links':[]}
        if tag=='a' and self.row is not None:self.anchor={'href':dict(attrs).get('href',''),'text':[]}
    def handle_data(self,data):
        if self.row is not None:self.row['text'].append(data)
        if self.anchor is not None:self.anchor['text'].append(data)
    def handle_endtag(self,tag):
        if tag=='a' and self.anchor is not None:
            if self.row is not None:self.row['links'].append(self.anchor)
            self.anchor=None
        if tag=='tr' and self.row is not None:self.rows.append(self.row);self.row=None

def get(url):
    # Only author/institution hosts selected in the public research are fetched.
    with httpx.Client(timeout=25,follow_redirects=True) as client:
        with client.stream('GET',url) as r:
            r.raise_for_status();parts=[];length=0
            for part in r.iter_bytes():
                length+=len(part)
                if length>12*1024*1024:raise ValueError('Document exceeds collection bound')
                parts.append(part)
            return str(r.url),b''.join(parts),r.headers.get('content-type','')

def check_document(url):
    try:
        final,data,mime=get(url)
        if not data.startswith(b'%PDF') and '/resources/' in url:
            text=data.decode('utf-8',errors='replace')
            links=re.findall(r'href=["\']([^"\']+\.pdf(?:\?[^"\']*)?)["\']',text)
            links=[urljoin(final,x) for x in links]
            if links:final,data,mime=get(links[0])
        if not data.startswith(b'%PDF'):
            return {'url':url,'final_url':final,'status':'non_pdf_or_access_gate','bytes':len(data)}
        reader=PdfReader(io.BytesIO(data))
        first=reader.pages[0].extract_text() or ''
        # Year comparison is a warning only; explicit review still required.
        years=sorted(set(re.findall(r'\b20\d{2}\b',first)))
        return {'url':url,'final_url':final,'status':'pdf_read','pages':len(reader.pages),
                'sha256':hashlib.sha256(data).hexdigest(),'first_page_years':years}
    except Exception as e:
        return {'url':url,'status':'unavailable','error_type':type(e).__name__}

def discover(family):
    key,title,courses,url=family
    try:
        final,data,_=get(url);parser=Tables();parser.feed(data.decode('utf-8',errors='replace'))
        found=[]
        for row in parser.rows:
            links=row['links']
            if len(links)<2:continue
            for i in range(len(links)-1):
                a,b=links[i:i+2]
                ta=' '.join(a['text']).strip().lower();tb=' '.join(b['text']).strip().lower()
                if not ('sol' in tb or 'answer' in tb or (ta in ('pdf','(pdf)') and tb in ('pdf','(pdf)'))):continue
                if 'sol' in ta or 'answer' in ta or not a['href'] or not b['href']:continue
                qa,sa=urljoin(final,a['href']),urljoin(final,b['href'])
                if qa==sa:continue
                # Keep first three pairs per family, not an unbounded crawl.
                found.append(dict(id=f'{key}-{len(found)+1:02d}',family=title,course_ids=courses,
                    index_url=final,label=' '.join(' '.join(row['text']).split())[:160],question_url=qa,solution_url=sa,
                    status='index_pair_confirmed',review_status='pending',language='en',
                    redistribution='link_only_pending_asset_license_review',approved_for_scoring=False))
                if len(found)==3:return found,[]
        return found,[] if found else [{'index':url,'reason':'no_pair_detected'}]
    except Exception as e:return [],[{'index':url,'reason':type(e).__name__}]

def main():
    if '--supplement' in sys.argv:
        supplement()
        return
    pairs=[];issues=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for found,failed in pool.map(discover,FAMILIES):pairs+=found;issues+=failed
    # Additional same-document question/answer sources read in the browser research.
    extras=[
      ('assembly','Harvard汇编练习',['C07'],'https://cs61.seas.harvard.edu/site/2026/AsmEx/'),
      ('cpp','LearnCpp第一章测验',['C06'],'https://www.learncpp.com/cpp-tutorial/chapter-1-summary-and-quiz/'),
      ('nlp','Stanford CS224N 2018期中题解',['C23','C21'],'https://web.stanford.edu/class/archive/cs/cs224n/cs224n.1184/midterm/cs224n-midterm-2018-solution.pdf'),
      ('rl','Stanford CS234收敛性习题解答',['C22'],'https://web.stanford.edu/class/archive/cs/cs234/cs234.1224/sessions/Problem_Sessions_CS234_Jan20_solutions.pdf'),
    ]
    for key,title,courses,url in extras:
        pairs.append(dict(id=key+'-01',family=title,course_ids=courses,index_url=url,label=title,
          question_url=url,solution_url=url,status='same_document_answers_read',review_status='pending',
          language='en',redistribution='link_only_pending_asset_license_review',approved_for_scoring=False))
    for year in (2024,2023):
        for exam in (1,2):
            stem=f'https://pdos.csail.mit.edu/6.824/quizzes/q{str(year)[2:]}-{exam}'
            pairs.append(dict(id=f'distributed-{year}-{exam}',family='MIT分布式系统考试',course_ids=['C26','C27'],
              index_url='https://pdos.csail.mit.edu/6.824/quizzes.html',label=f'{year} Exam {exam}',
              question_url=stem+'.pdf',solution_url=stem+'-sol.pdf',status='index_pair_confirmed',
              review_status='pending',language='en',redistribution='link_only_pending_asset_license_review',approved_for_scoring=False))
    urls=sorted({p[k] for p in pairs for k in ('question_url','solution_url')})
    docs={}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for url,result in zip(urls,pool.map(check_document,urls)):docs[url]=result
    for p in pairs:
        a,b=docs[p['question_url']],docs[p['solution_url']]
        p['question_document']=a;p['solution_document']=b
        if a['status']==b['status']=='pdf_read':
            p['status']='pdf_pair_read'
            if a['first_page_years'] and b['first_page_years'] and not set(a['first_page_years'])&set(b['first_page_years']):
                p['status']='year_mismatch_pending_review'
        elif p['status']!='same_document_answers_read':p['status']='attachments_unverified'
    data=dict(checked_on='2026-11-14',scope='题目与答案来源配对，尚未发布到正式题库',packs=pairs,collection_issues=issues,
      exclusions=[{'course_id':'C12','reason':'Stanford当前WA1标注2026，WA1sol标注2024，尚未确认题目逐项相同，不纳入可靠配对。'},
                  {'course_id':'C26','locator':'2024 Exam1 Q2','reason':'官方答案明确标注题目有误，不能用于自动评分。'}])
    path=OUT/'question-answer-sources.json';path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'packs':len(pairs),'pdf_pairs_read':sum(p['status']=='pdf_pair_read' for p in pairs),
        'same_document_sources':sum(p['status']=='same_document_answers_read' for p in pairs),
        'courses_with_candidates':len({c for p in pairs for c in p['course_ids']}),'collection_issues':issues}))

def supplement():
    path=OUT/'question-answer-sources.json';data=json.loads(path.read_text(encoding='utf-8'))
    base='https://ocw.mit.edu/courses/6-004-computation-structures-spring-2009/resources/'
    added=[]
    for key,title,courses,stem,answer in [
        ('comb','组合逻辑综合',['C05'],'mit6004s09tutor05','mit6004s09tutor05sol'),
        ('seq','时序逻辑与存储部件',['C05'],'mit6004s09tutor06','mit6004s09tutor06sol'),
        ('cache','缓存',['C09','C13'],'mit6_004s09_tutor16','mit6_004s09_tutor16_sol'),
        ('os','操作系统问题',['C10'],'mit6_004s09_tutor18','mit6_004s09_tutor18_sol'),
        ('semaphore','信号量',['C10'],'mit6_004s09_tutor20','mit6_004s09_tutor20_sol')]:
        added.append(dict(id='tutorial-'+key,family='MIT 6.004专题练习',label=title,course_ids=courses,
            index_url='https://ocw.mit.edu/courses/6-004-computation-structures-spring-2009/pages/tutorial-problems/',
            question_url=base+stem+'/',solution_url=base+answer+'/',review_status='pending',language='en',
            redistribution='link_only_pending_asset_license_review',approved_for_scoring=False))
    urls=[p[k] for p in added for k in ('question_url','solution_url')]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:docs=dict(zip(urls,pool.map(check_document,urls)))
    for p in added:
        a,b=docs[p['question_url']],docs[p['solution_url']]
        p.update(question_document=a,solution_document=b,status='pdf_pair_read' if a['status']==b['status']=='pdf_read' else 'attachments_unverified')
    old={p['id'] for p in added}
    data['packs']=[p for p in data['packs'] if p['id'] not in old]+added
    data['collection_issues']+=[{'index':'https://cs61c.org/fa26/resources/exams/','reason':'已核对2024春季试题与答案链接，附件跳转学校认证，不绕过登录。'}]
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'added_packs':len(added),'pdf_pairs_read':sum(p['status']=='pdf_pair_read' for p in added)}))

if __name__=='__main__':main()
