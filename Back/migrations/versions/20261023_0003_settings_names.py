"""Use conventional singleton settings table names.

Revision ID: 20261023_0003
Revises: 20261023_0002
"""
from alembic import op

revision = '20261023_0003'
down_revision = '20261023_0002'
branch_labels = None
depends_on = None


def upgrade():
    op.rename_table('system_settingss', 'system_settings')
    op.rename_table('queue_settingss', 'queue_settings')


def downgrade():
    op.rename_table('queue_settings', 'queue_settingss')
    op.rename_table('system_settings', 'system_settingss')
