"""Freeze the first PostgreSQL migration without connecting to any database.

Only use while preparing the initial release. Once applied, create a new revision
instead of regenerating an existing migration.
"""
from pathlib import Path

from sqlalchemy import create_mock_engine

from app.db.base import Base
from app.models import MODELS

ROOT = Path(__file__).resolve().parents[1]
if (ROOT / 'migrations/versions/20261023_0001_initial.py').exists():
    raise SystemExit('The initial migration is frozen. Create a new Alembic revision instead.')
statements = []


def capture(sql, *multiparams, **params):
    statements.append(str(sql.compile(dialect=engine.dialect)).strip())


engine = create_mock_engine('postgresql+psycopg://', capture)
Base.metadata.create_all(engine)

statements.append('''CREATE FUNCTION commerce_reject_immutable_change() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'immutable history cannot be updated or deleted' USING ERRCODE = '23514';
END;
$$''')
for name in ('resource_revisions', 'round_snapshots', 'performance_revisions', 'job_outputs'):
    statements.append(f'CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON {name} FOR EACH ROW EXECUTE FUNCTION commerce_reject_immutable_change()')

statements.append('''CREATE FUNCTION commerce_protect_job_input() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.input IS DISTINCT FROM OLD.input OR NEW.job_id IS DISTINCT FROM OLD.job_id THEN
        RAISE EXCEPTION 'job input snapshot is immutable' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$''')
statements.append('CREATE TRIGGER immutable_job_input BEFORE UPDATE ON job_runtime FOR EACH ROW EXECUTE FUNCTION commerce_protect_job_input()')

header = '''"""Initial relational schema and immutable-history guards.

Revision ID: 20261023_0001
Revises: none

Static PostgreSQL DDL is intentionally frozen here. Later model changes require
a new migration; this revision never imports runtime model definitions.
"""
from alembic import op

revision = '20261023_0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
'''
body = ''.join(f'    op.execute({statement!r})\n' for statement in statements)
body += '\n\ndef downgrade():\n'
# Explicit downgrade drops only the application-owned tables in this revision.
for name in reversed(list(Base.metadata.tables)):
    body += f'    op.execute("DROP TABLE IF EXISTS {name} CASCADE")\n'
body += '    op.execute("DROP FUNCTION IF EXISTS commerce_protect_job_input()")\n'
body += '    op.execute("DROP FUNCTION IF EXISTS commerce_reject_immutable_change()")\n'
path = ROOT / 'migrations/versions/20261023_0001_initial.py'
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(header + body, encoding='utf-8')
print(f'Frozen {len(Base.metadata.tables)} tables and {len(statements)} statements into {path.name}')
