"""Application entry point. Migrations/bootstrap are explicit deployment steps."""
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.contract_router import build_router
from app.api.v1.auth import router as auth_router
from app.api.v1 import catalog, workflows, competitors, imports
from app.core.contract import SPEC
from app.core.exceptions import register_exception_handlers
from app.services import users, settings, dashboard, files, media_generation, jobs, demo


app = FastAPI(title='电商运营助手', version=SPEC['info']['version'])
register_exception_handlers(app)


@app.middleware('http')
async def request_context(request: Request, call_next):
    request.state.request_id = str(uuid4())
    response = await call_next(request)
    response.headers['X-Request-ID'] = request.state.request_id
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


@app.get('/health', include_in_schema=False)
def health():
    return {'status': 'ok'}


HANDLERS = {}
for module in (catalog, workflows, competitors, imports, users, settings,
               dashboard, files, media_generation, jobs, demo):
    duplicates = set(HANDLERS) & set(module.HANDLERS)
    if duplicates:
        raise RuntimeError('Duplicate contract operation: ' + ', '.join(duplicates))
    HANDLERS.update(module.HANDLERS)

app.include_router(auth_router, prefix='/api/v1')
app.include_router(build_router(HANDLERS))
app.openapi = lambda: SPEC

if __name__ == '__main__':
    uvicorn.run(app="app.main:app", host='127.0.0.1', port=8000,reload=True)
