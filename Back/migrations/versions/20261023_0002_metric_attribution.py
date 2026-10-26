"""Allow platform attribution counts; report inconsistencies as warnings.

Revision ID: 20261023_0002
Revises: 20261023_0001
"""
from alembic import op

revision = '20261023_0002'
down_revision = '20261023_0001'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('ALTER TABLE performance_records DROP CONSTRAINT ck_performance_records_metric_counts')


def downgrade():
    # Will fail if newer records legitimately use the wider contract semantics;
    # an operator must reconcile such records before choosing this downgrade.
    op.execute('ALTER TABLE performance_records ADD CONSTRAINT ck_performance_records_metric_counts CHECK (clicks <= impressions AND conversions <= clicks)')
