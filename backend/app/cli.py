"""Explicit initialization and consistent offline backups."""
import argparse,getpass,hashlib,json,secrets,shutil,sqlite3
from pathlib import Path
from contextlib import closing
from alembic import command
from alembic.config import Config
from app.core.db import *
from app.core.security import password
from app.services.learning import QUESTIONS

def migrate():
    command.upgrade(Config(str(Path(__file__).resolve().parents[1]/'alembic.ini')),'head')

def initialize(demo=False):
    migrate()
    credentials=[]
    with transaction() as db:
        names=[('admin','管理员','admin')]
        if demo: names += [('teacher','陈老师','teacher'),('teacher2','王老师','teacher'),('student','张三','student'),('student2','李四','student')]
        ids={}
        for username,name,role in names:
            old=one(db,'SELECT id FROM users WHERE username=:u',u=username)
            if old: ids[username]=old['id'];continue
            raw=secrets.token_urlsafe(12);id=uid();ids[username]=id
            insert(db,'users',id=id,username=username,name=name,role=role,password_hash=password(raw),created_at=now())
            if role=='student': insert(db,'budgets',user_id=id)
            credentials.append((username,raw))
        if demo and not one(db,'SELECT 1 FROM classes'):
            cid=uid();insert(db,'classes',id=cid,owner_id=ids['teacher'],name='Python 程序设计 · 01 班',description='函数、递归与调用栈')
            cid2=uid();insert(db,'classes',id=cid2,owner_id=ids['teacher2'],name='数据结构 · 02 班',description='权限隔离验证班级')
            for u in ('student','student2'): insert(db,'memberships',class_id=cid,user_id=ids[u])
            body='''函数基础：Python使用def定义函数，return返回结果，参数传入函数。\n递归：函数调用自身，必须存在结束条件，每次调用逐步趋向基本情况。\n调用栈：函数调用将上下文压入栈中，返回时后进先出。无限递归导致栈深度错误。\n例：def factorial(n): return 1 if n == 0 else n * factorial(n-1)\n来源：本项目作者编写的教学样例，用于函数与递归基础主题。'''
            rid=uid();vid=uid();storage=uid()+'.txt';data=body.encode('utf-8');(DATA/'files'/storage).write_bytes(data)
            insert(db,'resources',id=rid,owner_id=ids['teacher'],class_id=cid,scope='class',title='Python函数与递归入门',description='函数、递归边界与调用栈',tags='Python 函数 递归 调用栈',source_license='项目自编教学资料，可用于本地演示',cloud_allowed=0,kind='text',status='published',current_version=vid,created_at=now())
            insert(db,'resource_versions',id=vid,resource_id=rid,filename='函数与递归.txt',storage_key=storage,mime='text/plain',bytes=len(data),hash=hashlib.sha256(data).hexdigest(),body=body,parse_status='ready',index_status='indexed',created_at=now())
            from app.api.resources import tokenize
            run(db,'INSERT INTO chunks VALUES(:r,:v,:b)',r=rid,v=vid,b=tokenize(body))
            audit(db,ids['admin'],'demo_initialized',cid)
    for username,raw in credentials: print(f'{username}: {raw} （首次登录必须改密，仅此次显示）')
    if not credentials: print('账号已存在，未修改密码或重复添加样例。')

def backup(destination):
    dest=Path(destination).resolve()
    if dest.exists(): raise SystemExit('备份目标须为尚不存在的独立目录')
    dest.mkdir(parents=True)
    # BEGIN IMMEDIATE blocks writers while SQLite backup and attachment manifest are copied.
    with transaction() as db:
        with closing(sqlite3.connect(DATA/'zhixing.db')) as source,closing(sqlite3.connect(dest/'zhixing.db')) as target:
            source.backup(target)
            target.commit()
        shutil.copytree(DATA/'files',dest/'files')
    manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (dest/'files').iterdir()}
    with closing(sqlite3.connect(dest/'zhixing.db')) as copied:
        tables=[row[0] for row in copied.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'chunks%'")]
        counts={table:copied.execute('SELECT count(*) FROM "'+table.replace('"','""')+'"').fetchone()[0] for table in tables}
        revision=copied.execute('SELECT version_num FROM alembic_version').fetchone()[0]
        configs=copied.execute('SELECT id,model,status,secret_env FROM model_configs').fetchall()
    metadata={'format_version':2,'created_at':now(),'app_version':'0.1.0','schema_revision':revision,
              'files':manifest,'database_sha256':hashlib.sha256((dest/'zhixing.db').read_bytes()).hexdigest(),
              'record_counts':counts,'config_references':[dict(zip(['id','model','status','secret_env'],row)) for row in configs]}
    (dest/'manifest.json').write_text(dump(metadata),encoding='utf-8')
    print('一致性备份已保存：',dest)

def restore(source,destination):
    src=Path(source).resolve();dest=Path(destination).resolve()
    if dest.exists(): raise SystemExit('恢复目标必须不存在，不能覆盖运行数据')
    manifest=json.loads((src/'manifest.json').read_text(encoding='utf-8'))
    for name,expected in manifest['files'].items():
        if Path(name).name!=name or hashlib.sha256((src/'files'/name).read_bytes()).hexdigest()!=expected: raise SystemExit('附件校验失败')
    expected_database=manifest.get('database_sha256')
    if expected_database and hashlib.sha256((src/'zhixing.db').read_bytes()).hexdigest()!=expected_database:
        raise SystemExit('数据库哈希校验失败')
    actual_names={p.name for p in (src/'files').iterdir()}
    if actual_names!=set(manifest['files']):raise SystemExit('附件清单不匹配')
    with closing(sqlite3.connect(src/'zhixing.db')) as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok': raise SystemExit('数据库校验失败')
        if db.execute('PRAGMA foreign_key_check').fetchall():raise SystemExit('外键一致性校验失败')
        for table,expected in manifest.get('record_counts',{}).items():
            if not table.replace('_','').isalnum():raise SystemExit('表清单不合法')
            if db.execute('SELECT count(*) FROM "'+table+'"').fetchone()[0]!=expected:
                raise SystemExit('记录数量校验失败')
        storage={row[0] for row in db.execute("SELECT storage_key FROM resource_versions WHERE storage_key IS NOT NULL AND storage_key!=''")}
        if not storage<=actual_names:raise SystemExit('资源引用缺少附件')
    shutil.copytree(src,dest)
    print('已恢复到独立目录；通过ZHIXING_DATA选择该目录后再启动：',dest)

def rebuild_index(directory):
    target=Path(directory).resolve()
    if target==DATA.resolve():raise SystemExit('请使用独立离线恢复目录重建索引')
    database=target/'zhixing.db'
    if not database.is_file():raise SystemExit('离线数据库不存在')
    from app.api.resources import tokenize
    with closing(sqlite3.connect(database)) as db:
        versions=db.execute("SELECT resource_id,id,body FROM resource_versions WHERE parse_status='ready' AND index_status='indexed'").fetchall()
        db.execute('DELETE FROM chunks')
        db.executemany('INSERT INTO chunks(resource_id,version_id,body) VALUES(?,?,?)',
                       [(resource,version,tokenize(body)) for resource,version,body in versions if body.strip()])
        db.commit()
        if db.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()[0]:
            raise SystemExit('离线数据库仍被占用，索引检查点未完成')
    manifest=target/'manifest.json'
    if manifest.exists():
        metadata=json.loads(manifest.read_text(encoding='utf-8'))
        metadata.update(database_sha256=hashlib.sha256(database.read_bytes()).hexdigest(),index_rebuilt_at=now())
        manifest.write_text(dump(metadata),encoding='utf-8')
    print('离线索引重建完成，版本数：',len(versions))

def prepare_models():
    from huggingface_hub import snapshot_download
    from fastembed import TextEmbedding
    from app.services.vector_index import MODEL_DIR,MODEL
    MODEL_DIR.mkdir(parents=True,exist_ok=True)
    snapshot_download('Systran/faster-whisper-tiny',local_dir=str(MODEL_DIR/'whisper-tiny'),allow_patterns=['*.json','*.bin','*.txt'])
    TextEmbedding(MODEL,cache_dir=str(MODEL_DIR/'embeddings'),threads=2)
    from app.services.media_extract import ocr_engine
    ocr_engine()
    print('本地OCR、语音和中文向量模型准备完成')


def create_demo_sandbox(directory):
    import os,subprocess,sys
    target=Path(directory).resolve()
    if target.exists():raise SystemExit('演示隔离目录必须尚不存在')
    target.mkdir(parents=True)
    environment={**os.environ,'ZHIXING_DATA':str(target)}
    result=subprocess.run([sys.executable,'-m','app.cli','demo'],env=environment)
    if result.returncode:raise SystemExit('演示初始化失败，已保留目录供排查')
    (target/'.demo-only.json').write_text(dump({'directory':str(target),'created_at':now()}),encoding='utf-8')
    print('独立演示目录已创建：',target)


def reset_demo_sandbox(directory,confirmation):
    target=Path(directory).resolve()
    default_data=Path(__file__).resolve().parents[1]/'data'
    marker=target/'.demo-only.json'
    if target==default_data.resolve() or not marker.is_file():raise SystemExit('仅可重置带标记的独立演示目录')
    metadata=json.loads(marker.read_text(encoding='utf-8'))
    if metadata.get('directory')!=str(target) or confirmation!=target.name:
        raise SystemExit('须使用--confirm填写演示目录名称，且目录标记必须匹配')
    archived=target.with_name(target.name+'-before-reset-'+uid())
    if archived.parent.resolve()!=target.parent.resolve() or target==target.parent:raise SystemExit('归档目标不合法')
    # An atomic sibling rename preserves all prior files and fails if Windows holds them open.
    try:target.rename(archived)
    except OSError:raise SystemExit('演示目录仍被占用或无法归档，请先停止使用该目录的服务')
    try:
        create_demo_sandbox(target)
    except BaseException:
        print('旧演示数据完整保留于：',archived)
        raise
    print('重置前数据已归档：',archived)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['init','demo','backup','restore','reindex','prepare-models','demo-sandbox','demo-reset','evaluate-cloud']);parser.add_argument('path',nargs='?');parser.add_argument('--destination');parser.add_argument('--confirm');parser.add_argument('--config-id');parser.add_argument('--operator')
    args=parser.parse_args()
    if args.action=='evaluate-cloud' and args.path and args.config_id and args.operator:
        from app.services.quality_evaluation import evaluate
        result=evaluate(args.config_id,args.path,args.operator)
        print('自动判据通过',result['automated_passed'],'/',result['total'],'，语义正确性仍需人工复核')
    elif args.action=='demo-sandbox' and args.path:create_demo_sandbox(args.path)
    elif args.action=='demo-reset' and args.path:reset_demo_sandbox(args.path,args.confirm)
    elif args.action=='prepare-models':prepare_models()
    elif args.action in ('init','demo'): initialize(args.action=='demo')
    elif args.action=='reindex' and args.path: rebuild_index(args.path)
    elif args.action=='backup' and args.path: backup(args.path)
    elif args.action=='restore' and args.path and args.destination: restore(args.path,args.destination)
    else: parser.error('backup需要目标目录；restore需要源目录和--destination')

if __name__=='__main__': main()
