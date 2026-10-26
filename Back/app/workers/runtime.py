"""Durable PostgreSQL workers: leases, private audit and atomic publication."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import re
import logging
import threading
from uuid import NAMESPACE_URL, uuid4, uuid5

from sqlalchemy import or_, select, text

from app.core.contract import validate_schema
from app.core.exceptions import ApiError
from app.core.security import utcnow
from app.db.session import SessionLocal
from app.models import MODELS
from app.services.common import Context
from app.services.jobs import event, timestamp

TEXT_KINDS = {"diagnosis", "main_image_plan", "video_script", "title_plan", "ad_recommendation", "review_report"}
LEASE_SECONDS = 90
logger = logging.getLogger(__name__)


def category(kind):
    return kind if kind in ("image", "video") else "text"


def instant(value):
    if not value:
        return None
    result = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result.astimezone(timezone.utc)


def context(db, user_id=None):
    ctx = Context(db=db, user={}, request_id=str(uuid4()))
    if user_id:
        user = ctx.get("User", user_id)
        if user["status"] != "active" or user["role"] not in ("admin", "operator"):
            raise ApiError(403, "FORBIDDEN", "任务提交用户当前已无执行权限")
        ctx.user = user
    return ctx


def clear_lease(ctx, job_id):
    ctx.repo.update("JobRuntime", job_id, {"lease_token": None, "lease_until": None}, bump=False)


def finish_cancelled(ctx, job):
    job = ctx.repo.update("GenerationJob", job["id"], {
        "job_status": "cancelled", "finished_at": timestamp(), "next_run_at": None,
        "error_code": "USER_CANCELLED", "error_message": "用户取消任务",
    })
    clear_lease(ctx, job["id"])
    event(ctx, job, "cancelled", "任务已取消，结果不发布")


def finish_timeout(ctx, job, runtime):
    records = runtime['provider_state'].get('media', [])
    unknown = job["job_kind"] in {"image", "video"} and any(item.get('submitting') and not item.get('task_id') for item in records)
    job = ctx.repo.update("GenerationJob", job["id"], {
        "job_status": "timeout", "finished_at": timestamp(), "next_run_at": None,
        "error_code": "PROVIDER_SUBMISSION_UNKNOWN" if unknown else "JOB_TIMEOUT",
        "error_message": "任务等待超时或执行进程失联",
    })
    clear_lease(ctx, job["id"])
    event(ctx, job, "timeout", job["error_message"])
    if job["job_kind"] == "public_link_parse":
        from app.workers.handlers.competitors import record_monitor_failure
        record_monitor_failure(ctx, runtime["input"], ApiError(409, "JOB_TIMEOUT", job["error_message"]))


def claim(*, only_job_ids=None):
    """Claim one due task. Optional ids support isolated integration verification."""
    with SessionLocal.begin() as db:
        if not db.scalar(text("SELECT pg_try_advisory_xact_lock(7310043)")):
            return None
        ctx = context(db)
        queue = ctx.get("QueueSettings", "singleton")
        model = MODELS["GenerationJob"]
        running = ctx.repo.list("GenerationJob", {"job_status": "running"})
        for group in ("text", "image", "video"):
            if sum(category(row["job_kind"]) == group for row in running) >= queue[group + "_concurrency"]:
                continue
            statement = select(model).where(
                model.job_status == "pending", model.dispatch_status == "queued",
                or_(model.next_run_at.is_(None), model.next_run_at <= utcnow()),
            )
            statement = statement.where(model.job_kind == group) if group in {"image", "video"} else statement.where(model.job_kind.notin_(["image", "video"]))
            if only_job_ids is not None:
                from uuid import UUID
                statement = statement.where(model.id.in_([UUID(str(identifier)) for identifier in only_job_ids]))
            candidates = db.scalars(statement.order_by(model.created_at, model.id).with_for_update(skip_locked=True).limit(30)).all()
            for candidate in candidates:
                job = ctx.get("GenerationJob", candidate.id)
                runtime = ctx.get("JobRuntime", job["id"], lock=True)
                if job["cancellation_requested"]:
                    finish_cancelled(ctx, job)
                    continue
                if job["deadline_at"] and instant(job["deadline_at"]) <= utcnow():
                    finish_timeout(ctx, job, runtime)
                    continue
                if job["attempts"] >= job["max_attempts"]:
                    job = ctx.repo.update("GenerationJob", job["id"], {
                        "job_status": "failed", "finished_at": timestamp(), "error_code": "MAX_ATTEMPTS_EXCEEDED",
                        "error_message": "已达到入队时确定的最大尝试次数",
                    })
                    clear_lease(ctx, job["id"])
                    event(ctx, job, "failed", job["error_message"])
                    continue
                lease = str(uuid4())
                now = utcnow()
                ctx.repo.update("JobRuntime", job["id"], {
                    "lease_token": lease, "lease_until": now + timedelta(seconds=LEASE_SECONDS), "heartbeat_at": now,
                }, bump=False)
                job = ctx.repo.update("GenerationJob", job["id"], {
                    "job_status": "running", "dispatch_status": "dispatched", "attempts": job["attempts"] + 1,
                    "started_at": now, "deadline_at": now + timedelta(seconds=runtime["input"].get("_timeout_seconds", 1800)),
                    "progress": 5, "error_code": None, "error_message": None, "next_run_at": None,
                })
                event(ctx, job, "running", "后台任务开始执行")
                return job["id"], lease
    return None


def still_owned(ctx, job_id, lease):
    """Lock and verify before every result write; an expired lease cannot revive."""
    job = ctx.get("GenerationJob", job_id, lock=True)
    runtime = ctx.get("JobRuntime", job_id, lock=True)
    if runtime["lease_token"] != lease or job["job_status"] != "running":
        event(ctx, job, "late_result_ignored", "任务执行权已失效，迟到结果不发布")
        return None
    if job["cancellation_requested"]:
        finish_cancelled(ctx, job)
        return None
    now = utcnow()
    if not runtime["lease_until"] or instant(runtime["lease_until"]) <= now or not job["deadline_at"] or instant(job["deadline_at"]) <= now:
        finish_timeout(ctx, job, runtime)
        event(ctx, ctx.get("GenerationJob", job_id), "late_result_ignored", "超时结果已隔离，不发布业务资源")
        return None
    return job, runtime


def heartbeat(job_id, lease, stop):
    while not stop.wait(15):
        try:
            with SessionLocal.begin() as db:
                ctx = context(db)
                if not still_owned(ctx, job_id, lease):
                    return
                now = utcnow()
                ctx.repo.update("JobRuntime", job_id, {"lease_until": now + timedelta(seconds=LEASE_SECONDS), "heartbeat_at": now}, bump=False)
        except Exception:
            # A failed heartbeat never extends the lease. No payload or credentials are logged.
            continue


def sanitized_audit(metadata, data):
    """Private raw model text is retained after removing known authentication material."""
    from app.llm.client import get_secret
    secret = get_secret(data.get("model_config", {}).get("secret_env_name"))
    def clean(value):
        if isinstance(value, dict):
            return {key: ("[REDACTED]" if key.lower() in {"authorization", "password", "api_key", "access_token", "secret"} else clean(item))
                    for key, item in value.items()}
        if isinstance(value, list):
            return [clean(item) for item in value]
        if isinstance(value, str):
            value = value.replace(secret, "[REDACTED]") if secret else value
            return re.sub(r"(?i)Bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [REDACTED]", value)
        return value
    return clean(deepcopy(metadata))


def record_model_call(ctx, job, data, metadata, error_code=None):
    config = data.get("model_config", {})
    identifier = str(uuid5(NAMESPACE_URL, f"commerce-model-call:{job['id']}:{job['attempts']}"))
    if ctx.repo.get("ModelCall", identifier):
        return
    metadata = sanitized_audit(metadata, data)
    usage = metadata.get("usage") or {}
    def count(key):
        value = usage.get(key)
        return min(value, 2147483647) if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None
    elapsed = metadata.get("elapsed_seconds")
    ctx.repo.create("ModelCall", {
        "id": identifier, "job_id": job["id"], "model_config_id": job.get("model_config_id"),
        "model_config_version": job.get("model_config_version"), "provider": config.get("provider", "unknown"),
        "model_name": config.get("model_name", "unknown")[:200], "prompt_version": data.get("prompt_version", "v1")[:100],
        "request_id": (metadata.get("provider_request_id") or "")[:200] or None,
        "input_tokens": count("prompt_tokens"), "output_tokens": count("completion_tokens"),
        "duration_ms": min(round(elapsed * 1000), 2147483647) if isinstance(elapsed, (int, float)) and elapsed >= 0 else None,
        "outcome": "failed" if error_code else "succeeded", "error_code": error_code,
    })
    runtime = ctx.get("JobRuntime", job["id"], lock=True)
    state = deepcopy(runtime["provider_state"])
    state.setdefault("text_audit", {})[str(job["attempts"])] = metadata
    ctx.repo.update("JobRuntime", job["id"], {"provider_state": state}, bump=False)


def persist_outputs(job, lease, data, outputs, metadata, *, model_called=False):
    with SessionLocal.begin() as db:
        ctx = context(db)
        # Audit the actual provider call even when cancellation won the result race.
        ctx.get("GenerationJob", job["id"], lock=True)
        if model_called:
            record_model_call(ctx, job, data, metadata)
        if not still_owned(ctx, job["id"], lease):
            return False
        runtime = ctx.get("JobRuntime", job["id"])
        state = {**runtime["result_state"], "outputs": outputs}
        ctx.repo.update("JobRuntime", job["id"], {"result_state": state}, bump=False)
        return True


def sync_assets(ctx, data, job):
    resources = {}
    for identifier in data["job_ids"]:
        source = ctx.get("GenerationJob", identifier)
        if source["product_id"] != job["product_id"] or source["job_kind"] not in {"image", "video"} or source["job_status"] != "succeeded":
            raise ApiError(409, "JOB_NOT_SUCCEEDED", "仅能补偿同步本商品已成功媒体任务")
        if source["round_id"]:
            ctx.require_round(source["product_id"], source["round_id"])
        for reference in source["result_resources"]:
            if reference["resource_type"] != "asset":
                continue
            asset = ctx.get("Asset", reference["resource_id"])
            if asset["product_id"] != job["product_id"] or asset["source_job_id"] != source["id"]:
                raise ApiError(409, "DEPENDENCY_CHANGED", "任务素材归属不一致")
            resources[asset["id"]] = {"resource_type": "asset", "resource_id": asset["id"], "version": asset["version"]}
    return list(resources.values())


def save_output_links(ctx, job, resources):
    kinds = {"diagnosis": "Diagnosis", "creative_plan": "CreativePlan", "asset": "Asset",
             "ad_recommendation": "AdRecommendation", "ad_experiment": "AdExperiment",
             "review_report": "ReviewReport", "parse_result": "ParseResult"}
    for index, reference in enumerate(resources):
        validate_schema("ResultResource", reference)
        if reference["resource_type"] not in kinds:
            raise ApiError(422, "JOB_EXECUTION_FAILED", "任务结果必须引用已保存的业务资源")
        row = ctx.get(kinds[reference["resource_type"]], reference["resource_id"])
        if reference["version"] is not None and row.get("version") != reference["version"]:
            raise ApiError(409, "DEPENDENCY_CHANGED", "发布资源版本不一致")
        if row.get("product_id") and row["product_id"] != job["product_id"]:
            # A workspace demo creates its own product. Only outputs of its
            # explicit child tasks may cross this workspace/product boundary.
            source_id = row.get("provenance", {}).get("source_job_id")
            source = ctx.repo.get("GenerationJob", source_id) if source_id else None
            source_runtime = ctx.repo.get("JobRuntime", source_id) if source else None
            demo_child = (job["job_kind"] == "demo_data" and job["execution_mode"] == "demo"
                          and source and source["execution_mode"] == "demo" and source["job_status"] == "succeeded"
                          and source["product_id"] == row["product_id"] and source_runtime
                          and source_runtime["input"].get("demo_parent_job_id") == job["id"])
            if not demo_child:
                raise ApiError(409, "DEPENDENCY_CHANGED", "发布资源商品归属不一致")
        existing = ctx.repo.list("JobOutput", {"job_id": job["id"], "output_index": index})
        if existing:
            if existing[0]["resource_id"] != reference["resource_id"] or existing[0]["resource_type"] != reference["resource_type"]:
                raise ApiError(409, "DEPENDENCY_CHANGED", "同一任务输出序号已登记其他资源")
        else:
            ctx.repo.create("JobOutput", {"job_id": job["id"], "output_index": index,
                                          "resource_type": reference["resource_type"], "resource_id": reference["resource_id"]})


def publish(ctx, job, data, outputs):
    kind = job["job_kind"]
    if kind in {'image', 'video'}:
        from app.workers.handlers.media import publish_media
        return publish_media(ctx, job, data, outputs)
    if kind in TEXT_KINDS:
        from app.workers.handlers.text import publish_text
        return publish_text(ctx, job, data, outputs)
    if kind == "ad_experiment":
        from app.services.ad_experiments import execute_experiments
        return execute_experiments(ctx, job, data)
    if kind == "public_link_parse":
        from app.workers.handlers.competitors import publish_parse
        return publish_parse(ctx, job, data, outputs)
    if kind == "timeout_sweep":
        count = sweep_timeouts(ctx, exclude=job["id"])
        event(ctx, job, "progress", f"已处理 {count} 个超时任务")
        return []
    if kind == "competitor_monitor_sweep":
        from app.services.competitors import process_due_monitors
        count = process_due_monitors(ctx)
        event(ctx, job, "progress", f"已调度 {count} 个竞品监控任务")
        return []
    if kind == "asset_sync":
        return sync_assets(ctx, data, job)
    if kind == "demo_data":
        from app.services.demo import execute_demo
        return execute_demo(ctx, job, data)
    raise ApiError(422, "JOB_EXECUTION_FAILED", "任务类型尚未配置执行器")


def compensate_demo(job_id, attempt):
    """Delete deterministic objects only after a confirmed failed publication.

    Keep the job locked during cleanup so retry cannot publish the same keys.
    An ambiguous database commit or a newer attempt is left for reconciliation.
    """
    try:
        with SessionLocal.begin() as db:
            ctx = context(db)
            job = ctx.get("GenerationJob", job_id, lock=True)
            if (job["job_kind"] != "demo_data" or job["job_status"] not in {"failed", "cancelled", "timeout"}
                    or job["attempts"] != attempt):
                return
            from app.services.demo_dataset import cleanup_demo_objects
            cleanup_demo_objects(job_id)
    except Exception:
        logger.error("Demo cleanup requires reconciliation for job %s", job_id)


def fail_job(job_id, lease, error, *, original_job=None, data=None, model_called=False):
    code = getattr(error, "code", "JOB_EXECUTION_FAILED")
    message = getattr(error, "message", "任务执行失败，请查看请求编号并重试")[:4000]
    with SessionLocal.begin() as db:
        ctx = context(db)
        job = ctx.get("GenerationJob", job_id, lock=True)
        runtime = ctx.get("JobRuntime", job_id, lock=True)
        data = data or runtime["input"]
        if model_called and original_job:
            record_model_call(ctx, original_job, data, getattr(error, "audit_metadata", {}), code)
        owned = still_owned(ctx, job_id, lease)
        if not owned:
            return
        job, runtime = owned
        retryable = bool(getattr(error, "retryable", False))
        safe = job["job_kind"] in TEXT_KINDS | {"public_link_parse"} and retryable and job["attempts"] < job["max_attempts"]
        changes = {"error_code": code, "error_message": message, "job_status": "failed", "finished_at": timestamp(), "next_run_at": None}
        if safe:
            changes.update(job_status="pending", dispatch_status="queued", finished_at=None,
                           next_run_at=utcnow() + timedelta(seconds=30 if job["attempts"] == 1 else 120),
                           queued_at=timestamp(), deadline_at=utcnow() + timedelta(hours=24))
        job = ctx.repo.update("GenerationJob", job_id, changes)
        clear_lease(ctx, job_id)
        if job["job_kind"] == "public_link_parse":
            from app.workers.handlers.competitors import record_monitor_failure
            record_monitor_failure(ctx, data, error)
        event(ctx, job, "retry_scheduled" if safe else "failed", message)


def run_job(job_id, lease):
    stop = threading.Event()
    thread = threading.Thread(target=heartbeat, args=(job_id, lease, stop), daemon=True)
    thread.start()
    job = data = None
    model_called = False
    demo_attempt = None
    try:
        with SessionLocal.begin() as db:
            ctx = context(db)
            owned = still_owned(ctx, job_id, lease)
            if not owned:
                return
            job, runtime = owned
            context(db, job["submitted_by"])
            data = runtime["input"]
        kind = job["job_kind"]
        outputs = runtime["result_state"].get("outputs")
        metadata = {}
        if kind in TEXT_KINDS and outputs is None:
            from app.workers.handlers.text import execute_text_with_metadata
            model_called = True
            outputs, metadata = execute_text_with_metadata(kind, data, data["model_config"])
        elif kind == "public_link_parse" and outputs is None:
            from app.workers.handlers.competitors import execute_parse
            outputs = execute_parse(data)
        elif kind in {"image", "video"} and outputs is None:
            from app.workers.handlers.media import execute_media
            model_called = True
            outputs, metadata = execute_media(job, lease, data)
        if outputs is not None:
            if not persist_outputs(job, lease, data, outputs, metadata, model_called=model_called):
                return
            model_called = False
        with SessionLocal.begin() as db:
            ctx = context(db, job["submitted_by"])
            if job["product_id"]:
                ctx.require_product(job["product_id"], lock=True)
            owned = still_owned(ctx, job_id, lease)
            if not owned:
                return
            job, _ = owned
            if job["round_id"]:
                ctx.require_round(job["product_id"], job["round_id"])
            if kind == "demo_data":
                demo_attempt = job["attempts"]
            resources = publish(ctx, job, data, outputs)
            if not still_owned(ctx, job_id, lease):
                # Roll back all just-created business rows before fail_job
                # persists cancellation/timeout in a fresh transaction.
                raise ApiError(409, "JOB_TIMEOUT", "结果发布前执行权已失效")
            save_output_links(ctx, job, resources)
            job = ctx.repo.update("GenerationJob", job_id, {
                "job_status": "succeeded", "progress": 100, "finished_at": timestamp(),
                "result_resources": resources, "error_code": None, "error_message": None,
            })
            clear_lease(ctx, job_id)
            event(ctx, job, "succeeded", "结果已保存")
    except Exception as error:
        fail_job(job_id, lease, error, original_job=job, data=data, model_called=model_called)
    finally:
        stop.set()
        thread.join(timeout=1)
        if demo_attempt is not None:
            compensate_demo(job_id, demo_attempt)
        if job and job['job_kind'] in {'image', 'video'}:
            from app.workers.handlers.media import cleanup_unpublished
            cleanup_unpublished(job_id)


def sweep_timeouts(ctx, exclude=None, *, only_job_ids=None):
    if not ctx.db.scalar(text("SELECT pg_try_advisory_xact_lock(7310044)")):
        return 0
    count = 0
    now = utcnow()
    filters = {"job_status": ["pending", "running"]}
    if only_job_ids is not None:
        filters["id"] = only_job_ids
    for candidate in ctx.repo.list("GenerationJob", filters, order="id"):
        if candidate["id"] == exclude:
            continue
        job = ctx.get("GenerationJob", candidate["id"], lock=True)
        if job["job_status"] not in {"pending", "running"}:
            continue
        runtime = ctx.get("JobRuntime", job["id"], lock=True)
        if job["cancellation_requested"]:
            finish_cancelled(ctx, job)
            count += 1
            continue
        expired = bool(job["deadline_at"] and instant(job["deadline_at"]) <= now)
        stale = job["job_status"] == "running" and (not runtime["lease_until"] or instant(runtime["lease_until"]) <= now)
        if expired or stale:
            finish_timeout(ctx, job, runtime)
            count += 1
    return count
