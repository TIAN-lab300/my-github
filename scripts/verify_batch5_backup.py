"""CLI acceptance for an isolated fifth-batch database."""
import json,os,sqlite3,hashlib
from pathlib import Path
from uuid import uuid4
root=Path(__file__).resolve().parents[1]
os.environ['ZHIXING_DATA']=str(root/'backend/data/batch5-final2')
from app.cli import backup,restore,rebuild_index
directory=root/'backend/data/batch5-artifacts'/uuid4().hex
source=directory/'backup';target=directory/'restored'
backup(source)
manifest=json.loads((source/'manifest.json').read_text(encoding='utf-8'))
restore(source,target)
rebuild_index(target)
with sqlite3.connect(target/'zhixing.db') as db:
    assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    assert db.execute('PRAGMA foreign_key_check').fetchall()==[]
    for table,count in manifest['record_counts'].items():
        assert db.execute('SELECT count(*) FROM "'+table+'"').fetchone()[0]==count
    assert db.execute("SELECT count(*) FROM chunks WHERE chunks MATCH 'recursion'").fetchone()[0]>0
for filename,digest in manifest['files'].items():
    assert hashlib.sha256((target/'files'/filename).read_bytes()).hexdigest()==digest
results=[
 {'id':'SF-OPS-04','status':'passed','actual':'CLI生成数据库、附件、配置引用、版本及SHA-256清单，备份源为独立验收库'},
 {'id':'SF-OPS-05','status':'passed','actual':'CLI独立目录恢复，记录数量/附件hash/外键核对通过，索引重建后真实关键词命中'}]
(root/'docs/evidence/implementation/batch5-cli.json').write_text(json.dumps({'results':results,'schema_revision':manifest['schema_revision'],'table_count':len(manifest['record_counts']),'attachment_count':len(manifest['files'])},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Two CLI acceptance functions passed')
