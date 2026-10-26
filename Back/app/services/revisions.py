from app.services.common import ApiError
from app.services.ai_support import RESOURCE_TYPES, owned


def list_revisions(ctx):
    kind = RESOURCE_TYPES[ctx.query["resource_type"]]
    owned(ctx, kind, ctx.query["resource_id"])
    return ctx.collection("ResourceRevision", {
        "product_id": ctx.params["product_id"], "resource_type": ctx.query["resource_type"],
        "resource_id": ctx.query["resource_id"],
    })


def get_revision(ctx):
    row = ctx.get("ResourceRevision", ctx.params["revision_id"])
    if row["resource"]["product_id"] != ctx.params["product_id"]:
        raise ApiError(404, "NOT_FOUND", "资源不存在")
    return row


HANDLERS = {
    "GET /products/{product_id}/resource-revisions": list_revisions,
    "GET /products/{product_id}/resource-revisions/{revision_id}": get_revision,
}
