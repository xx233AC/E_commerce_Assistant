from app.core.exceptions import ApiError

ASSET_TRANSITIONS = {'pending': {'approved', 'rejected'}, 'approved': {'rejected'}, 'rejected': {'pending'}}
EXPERIMENT_TRANSITIONS = {'draft': {'confirmed', 'cancelled'}, 'confirmed': {'running', 'cancelled'}, 'running': {'finished', 'cancelled'}, 'finished': set(), 'cancelled': set()}


def require_transition(current, target, transitions):
    if target not in transitions.get(current, set()):
        raise ApiError(409, 'INVALID_STATE_TRANSITION', f'不允许从 {current} 变为 {target}')
