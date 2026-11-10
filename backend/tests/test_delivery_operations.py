from pathlib import Path
import sqlite3
from contextlib import closing
import pytest
from app.cli import create_demo_sandbox,reset_demo_sandbox


def test_demo_reset_requires_marker_and_preserves_archive(tmp_path):
    target=tmp_path/'isolated-demo'
    with pytest.raises(SystemExit):reset_demo_sandbox(target,'isolated-demo')
    create_demo_sandbox(target)
    with closing(sqlite3.connect(target/'zhixing.db')) as database:
        original=database.execute("SELECT id FROM users WHERE username='admin'").fetchone()[0]
    with pytest.raises(SystemExit):reset_demo_sandbox(target,'wrong-confirmation')
    assert (target/'zhixing.db').exists()
    reset_demo_sandbox(target,'isolated-demo')
    archives=list(tmp_path.glob('isolated-demo-before-reset-*'))
    assert len(archives)==1
    with closing(sqlite3.connect(archives[0]/'zhixing.db')) as database:
        assert database.execute("SELECT id FROM users WHERE username='admin'").fetchone()[0]==original
    with closing(sqlite3.connect(target/'zhixing.db')) as database:
        assert database.execute("SELECT id FROM users WHERE username='admin'").fetchone()[0]!=original
