"""Back up the configured SQLite database, migrate and record question checks."""
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
import sqlite3

from app.cli import migrate
from app.core.db import DATA, rows, transaction
from app.services.curriculum_governance import check_question


def main():
    source=DATA/'zhixing.db'
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup=DATA/'migration-backups'/f'before-curriculum-upgrade-{stamp}.sqlite3'
    backup.parent.mkdir(exist_ok=True)
    with closing(sqlite3.connect(source.resolve().as_uri()+'?mode=ro',uri=True)) as original:
        with closing(sqlite3.connect(backup)) as copy:
            original.backup(copy)
            if copy.execute('PRAGMA quick_check').fetchall()!=[('ok',)]:
                raise RuntimeError('数据库备份完整性检查失败')
    print('backup',backup,flush=True)
    migrate()
    with transaction() as db:
        violations=rows(db,'PRAGMA foreign_key_check')
        if violations:
            raise RuntimeError(f'存在 {len(violations)} 条外键违规')
        counts=Counter()
        for item in rows(db,"SELECT id FROM learning_question_versions WHERE status='published' ORDER BY id"):
            counts[check_question(db,item['id'],reuse=True)['status']]+=1
        print('structural_validation',dict(counts),flush=True)


if __name__=='__main__':
    main()
