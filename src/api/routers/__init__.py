from fastapi import APIRouter

from src.api.routers.admin_console_router import router as admin_console_router
from src.api.routers.auth_router import router as auth_router
from src.api.routers.blocker_router import router as blocker_router
from src.api.routers.chat_router import router as chat_router
from src.api.routers.knowledge_document_router import router as knowledge_document_router
from src.api.routers.member_onboarding_router import router as member_onboarding_router
from src.api.routers.my_policy_router import router as my_policy_router
from src.api.routers.onboarding_plan_router import router as onboarding_plan_router
from src.api.routers.onboarding_template_router import router as onboarding_template_router
from src.api.routers.plan_task_router import router as plan_task_router
from src.api.routers.pm_dashboard_router import router as pm_dashboard_router
from src.api.routers.pm_progress_router import router as pm_progress_router
from src.api.routers.project_discovery_router import router as project_discovery_router
from src.api.routers.project_membership_router import router as project_membership_router
from src.api.routers.project_router import router as project_router
from src.api.routers.rule_review_router import router as rule_review_router
from src.api.routers.task_dependency_router import router as task_dependency_router
from src.api.routers.template_task_router import router as template_task_router
from src.api.routers.template_version_router import router as template_version_router
from src.api.routers.user_router import router as user_router

api_router = APIRouter()
api_router.include_router(member_onboarding_router)
api_router.include_router(blocker_router)
api_router.include_router(admin_console_router)
api_router.include_router(auth_router)
api_router.include_router(my_policy_router)
api_router.include_router(user_router)
api_router.include_router(project_router)
api_router.include_router(project_membership_router)
api_router.include_router(onboarding_plan_router)
api_router.include_router(plan_task_router)
api_router.include_router(onboarding_template_router)
api_router.include_router(template_version_router)
api_router.include_router(template_task_router)
api_router.include_router(task_dependency_router)
api_router.include_router(knowledge_document_router)
api_router.include_router(chat_router)
api_router.include_router(pm_progress_router)
api_router.include_router(pm_dashboard_router)
api_router.include_router(rule_review_router)
api_router.include_router(project_discovery_router)
