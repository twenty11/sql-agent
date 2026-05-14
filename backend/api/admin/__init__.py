from api.admin.users import router as users_router
from api.admin.audit import router as audit_router
from api.admin.vectorstore import router as vectorstore_router
from api.admin.roles import router as roles_router
from api.admin.tables import router as tables_router

__all__ = [
    "users_router",
    "audit_router",
    "vectorstore_router",
    "roles_router",
    "tables_router",
]
