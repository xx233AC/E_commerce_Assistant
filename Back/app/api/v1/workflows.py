"""Contract route handlers; the central router supplies auth, schema and transaction checks."""
from app.services import rounds, diagnoses, creative, ad_recommendations, reviews, revisions

HANDLERS = {
    **rounds.HANDLERS, **diagnoses.HANDLERS, **creative.HANDLERS,
    **ad_recommendations.HANDLERS, **reviews.HANDLERS, **revisions.HANDLERS,
}
