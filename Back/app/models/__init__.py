from app.models.store import Store, PlatformAccount, AuthorizationSession
from app.models.product import Product, PlatformMapping
from app.models.inventory import Sku, Inventory, InventoryMovement
from app.models.competitor import Competitor, CompetitorMonitor, MonitorSnapshot, ParseResult
from app.models.round import OperatingRound, RoundSnapshot
from app.models.diagnosis import Diagnosis
from app.models.creative import CreativePlan
from app.models.job import GenerationJob, JobEvent
from app.models.file import FileObject
from app.models.asset import Asset
from app.models.promotion_link import PromotionLink
from app.models.ad_recommendation import AdRecommendation, Confirmation
from app.models.ad_experiment import AdExperiment
from app.models.performance import PerformanceRecord
from app.models.review import ReviewReport
from app.models.revision import ResourceRevision
from app.models.import_batch import ImportBatch
from app.models.settings import ModelConfig, SystemSettings, QueueSettings
from app.models.audit_log import AuditLog
from app.models.internal import *

MODELS = {
    'Store': Store,
    'PlatformAccount': PlatformAccount,
    'AuthorizationSession': AuthorizationSession,
    'Product': Product,
    'PlatformMapping': PlatformMapping,
    'Sku': Sku,
    'Inventory': Inventory,
    'InventoryMovement': InventoryMovement,
    'Competitor': Competitor,
    'CompetitorMonitor': CompetitorMonitor,
    'MonitorSnapshot': MonitorSnapshot,
    'ParseResult': ParseResult,
    'OperatingRound': OperatingRound,
    'RoundSnapshot': RoundSnapshot,
    'Diagnosis': Diagnosis,
    'CreativePlan': CreativePlan,
    'GenerationJob': GenerationJob,
    'JobEvent': JobEvent,
    'FileObject': FileObject,
    'Asset': Asset,
    'PromotionLink': PromotionLink,
    'AdRecommendation': AdRecommendation,
    'Confirmation': Confirmation,
    'AdExperiment': AdExperiment,
    'PerformanceRecord': PerformanceRecord,
    'ReviewReport': ReviewReport,
    'ResourceRevision': ResourceRevision,
    'ImportBatch': ImportBatch,
    'ModelConfig': ModelConfig,
    'SystemSettings': SystemSettings,
    'QueueSettings': QueueSettings,
    'AuditLog': AuditLog,
}

# The authentication model is maintained separately from generated business tables.
from app.models.user import User
from app.models.session import LoginSession
from app.models.login_limit import LoginLimit
User.SCHEMA_NAME = 'User'
User.__dto_fields__ = ('id', 'version', 'created_at', 'updated_at', 'username', 'display_name', 'role', 'status', 'last_login_at')
User.__pk_field__ = 'id'
User.__ref_fields__ = {}
User.__money_fields__ = ()
User.__ratio_fields__ = ()
User.__computed_fields__ = ()
MODELS['User'] = User
MODELS.update(INTERNAL_MODELS)
