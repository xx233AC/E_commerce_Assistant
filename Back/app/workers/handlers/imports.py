"""Import worker owns its transactions; partial mode commits one row at a time."""
import copy
import hashlib
import secrets
from dataclasses import replace
from datetime import timedelta

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ApiError
from app.services import imports


def _actor(ctx, state, committing=False):
    user_id = state['commit_options'].get('user_id') if committing else state['context']['user_id']
    user = ctx.get('User', user_id)
    if user['status'] != 'active' or user['role'] not in {'admin', 'operator'}:
        raise ApiError(403, 'FORBIDDEN', '导入发起账号已停用或失去写权限')
    return replace(ctx, user=user)


def _preview(ctx, batch, state):
    from app.services.files import read_bytes
    file = ctx.get('FileObject', batch['file_id'])
    data = read_bytes(ctx, file['id'])
    if hashlib.sha256(data).hexdigest() != state['context']['sha256']:
        raise ApiError(409, 'IMPORT_FILE_CHANGED', '文件内容与批次绑定的 SHA256 不一致')
    settings = ctx.repo.get('SystemSettings', 'singleton')
    maximum = min(settings['max_import_rows'] if settings else 10000, 10000)
    parsed = imports.parse_file(data, file['content_type'], batch['import_type'], state['context'].get('column_mappings', []), maximum)
    seen, rows = {}, []
    for raw in parsed:
        number, cells = raw['row_number'], raw['raw']
        row = {'row_number': number, 'valid': True,
            'cells': [{'field': key, 'value': str(value) if value is not None else None} for key, value in cells.items()],
            'errors': [], 'payload': None, 'commit_status': 'pending', 'commit_errors': []}
        try:
            payload, key = imports.prepare_row(ctx, batch, state['context'], cells)
            row['payload'] = payload
            if key in seen:
                # Mark both copies invalid; file order cannot pick a winner.
                original = rows[seen[key]]
                duplicate_error = imports.row_error(number, 'row', 'DUPLICATE_IMPORT_ROW', '同文件包含重复业务行')
                row['errors'].append(duplicate_error)
                if not any(e['code'] == 'DUPLICATE_IMPORT_ROW' for e in original['errors']):
                    original['errors'].append(imports.row_error(original['row_number'], 'row', 'DUPLICATE_IMPORT_ROW', '同文件包含重复业务行'))
                    original['valid'] = False
            else:
                seen[key] = len(rows)
        except ApiError as exc:
            row['errors'] = imports.exception_errors(exc, number)
        row['valid'] = not row['errors']
        rows.append(row)
    valid = sum(row['valid'] for row in rows)
    ctx.repo.update('ImportState', batch['id'], {'rows': rows}, bump=False)
    ctx.repo.update('ImportBatch', batch['id'], {
        'status': 'preview_ready', 'total_rows': len(rows), 'valid_rows': valid,
        'invalid_rows': len(rows) - valid, 'errors_count': sum(len(r['errors']) for r in rows),
        'preview_token': secrets.token_urlsafe(40), 'preview_expires_at': imports.now() + timedelta(minutes=30),
    })
    ctx.db.commit()


def _terminal(ctx, batch_id, rows, error_message=None):
    succeeded = sum(r.get('commit_status') == 'succeeded' for r in rows)
    status = 'succeeded' if succeeded == len(rows) and rows else 'partially_succeeded' if succeeded else 'failed'
    ctx.repo.update('ImportState', batch_id, {'rows': rows}, bump=False)
    ctx.repo.update('ImportBatch', batch_id, {
        'status': status, 'succeeded_rows': succeeded, 'failed_rows': len(rows) - succeeded,
        'errors_count': sum(len(r.get('errors', [])) + len(r.get('commit_errors', [])) for r in rows),
        'error_message': error_message,
    })


def _partial(ctx, batch, state):
    rows = copy.deepcopy(state['rows'])
    # Each committed success is permanently paired with the resulting business row.
    # A crash can replay only still-pending rows, never successful stock increments.
    for index, row in enumerate(rows):
        if row.get('commit_status') in {'succeeded', 'failed'}:
            continue
        ctx.get('ImportBatch', batch['id'], lock=True)
        if not row['valid']:
            row['commit_status'] = 'failed'
            row['commit_errors'] = [imports.row_error(row['row_number'], 'row', 'PREVIEW_ROW_INVALID', '此行预览无效，未尝试写入')]
        else:
            try:
                actor = _actor(ctx, state, committing=True)
                result = imports.apply_row(actor, batch, state['context'], row['payload'])
                value = result.data if hasattr(result, 'data') else result
                row['resource_id'] = value.get('id') if isinstance(value, dict) else None
                row['commit_status'] = 'succeeded'
            except (ApiError, IntegrityError) as exc:
                ctx.db.rollback()
                ctx.get('ImportBatch', batch['id'], lock=True)
                row['commit_status'] = 'failed'
                row['commit_errors'] = imports.exception_errors(exc, row['row_number'])
        ctx.repo.update('ImportState', batch['id'], {'rows': rows}, bump=False)
        ctx.repo.update('ImportBatch', batch['id'], {
            'succeeded_rows': sum(r.get('commit_status') == 'succeeded' for r in rows),
            'failed_rows': sum(r.get('commit_status') == 'failed' for r in rows),
        })
        ctx.db.commit()
    ctx.get('ImportBatch', batch['id'], lock=True)
    _terminal(ctx, batch['id'], rows)
    ctx.db.commit()


def _atomic(ctx, batch, state):
    rows = copy.deepcopy(state['rows'])
    try:
        actor = _actor(ctx, state, committing=True)
        for row in rows:
            if not row['valid']:
                raise ApiError(409, 'IMPORT_HAS_ERRORS', '全量提交不接受预览错误行')
            result = imports.apply_row(actor, batch, state['context'], row['payload'])
            value = result.data if hasattr(result, 'data') else result
            row['resource_id'] = value.get('id') if isinstance(value, dict) else None
            row['commit_status'] = 'succeeded'
        _terminal(ctx, batch['id'], rows)
        ctx.db.commit()
    except (ApiError, IntegrityError) as exc:
        ctx.db.rollback()
        ctx.get('ImportBatch', batch['id'], lock=True)
        rows = copy.deepcopy(state['rows'])
        for row in rows:
            row['commit_status'] = 'failed'
            row['commit_errors'] = imports.exception_errors(exc, row['row_number'])
        _terminal(ctx, batch['id'], rows, '全量导入发生冲突，所有业务写入已回滚')
        ctx.db.commit()


def _run(ctx, batch_id):
    try:
        batch = ctx.get('ImportBatch', batch_id, lock=True)
        state = ctx.get('ImportState', batch_id)
        if batch['status'] == 'validating':
            _preview(_actor(ctx, state), batch, state)
        elif batch['status'] == 'committing':
            if state['commit_options'].get('allow_partial'):
                _partial(ctx, batch, state)
            else:
                _atomic(ctx, batch, state)
        else:
            ctx.db.rollback()
    except Exception as exc:
        ctx.db.rollback()
        batch = ctx.repo.get('ImportBatch', batch_id, lock=True)
        if batch and batch['status'] in {'validating', 'committing'}:
            message = exc.message if isinstance(exc, ApiError) else '导入处理失败，请检查文件内容或服务连接后新建批次'
            state = ctx.get('ImportState', batch_id)
            if batch['status'] == 'committing':
                rows = state['rows']
                for row in rows:
                    if row.get('commit_status') != 'succeeded':
                        row['commit_status'] = 'failed'
                        row['commit_errors'] = imports.exception_errors(exc, row['row_number'])
                _terminal(ctx, batch_id, rows, message)
            else:
                ctx.repo.update('ImportBatch', batch_id, {'status': 'failed', 'error_message': message})
            ctx.db.commit()


def process_import(ctx, batch_id):
    """Worker-only entry; the supplied session must have no uncommitted writes."""
    # Pin a physical connection so the session advisory lock survives per-row
    # commits. The ordinary caller session only selected candidate batch IDs.
    bind = ctx.db.get_bind()
    engine = getattr(bind, 'engine', bind)
    ctx.db.rollback()
    lock_key = int.from_bytes(hashlib.sha256(str(batch_id).encode()).digest()[:8], 'big', signed=True)
    with engine.connect() as connection:
        acquired = connection.scalar(text('SELECT pg_try_advisory_lock(:key)'), {'key': lock_key})
        connection.commit()
        if not acquired:
            return
        try:
            with Session(bind=connection, expire_on_commit=False) as db:
                _run(replace(ctx, db=db), batch_id)
        finally:
            if connection.in_transaction():
                connection.rollback()
            connection.execute(text('SELECT pg_advisory_unlock(:key)'), {'key': lock_key})
            connection.commit()
