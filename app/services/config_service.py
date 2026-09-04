"""
System Configuration Service Layer
Manages typed system configuration parameters with audit trails (Secrets strictly barred from database).
"""

import json
from datetime import datetime, timezone
from typing import Any, List, Optional, Tuple
from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload
from app.core.exceptions import EntityNotFoundException, ValidationException
from app.core.logging import get_logger
from app.models.governance import ConfigValueType, SystemConfig
from app.schemas.governance import SystemConfigCreate, SystemConfigUpdate
from app.services.audit_service import AuditService

logger = get_logger(__name__)


class SystemConfigService:
    """Manages typed system configuration repository."""

    def __init__(self, db: Session):
        self.db = db
        self.audit = AuditService(db)

    def validate_typed_value(self, value: str, value_type: ConfigValueType) -> str:
        """Validates that string value conforms to declared type."""
        val_str = value.strip()
        if value_type == ConfigValueType.INTEGER:
            try:
                int(val_str)
            except ValueError:
                raise ValidationException(f"Configuration value '{value}' must be a valid integer")
        elif value_type == ConfigValueType.FLOAT:
            try:
                float(val_str)
            except ValueError:
                raise ValidationException(f"Configuration value '{value}' must be a valid float")
        elif value_type == ConfigValueType.BOOLEAN:
            if val_str.lower() not in ["true", "false", "1", "0", "yes", "no"]:
                raise ValidationException(f"Configuration value '{value}' must be a valid boolean")
        elif value_type == ConfigValueType.JSON:
            try:
                json.loads(val_str)
            except Exception as e:
                raise ValidationException(f"Configuration value must be valid JSON: {str(e)}")
        return val_str

    def create_config(self, data: SystemConfigCreate, actor_id: UUID) -> SystemConfig:
        existing = self.db.scalar(select(SystemConfig).where(SystemConfig.key == data.key))
        if existing:
            raise ValidationException(f"Configuration key '{data.key}' already exists")

        clean_val = self.validate_typed_value(data.value, data.value_type)

        config = SystemConfig(
            key=data.key,
            value=clean_val,
            value_type=data.value_type,
            description=data.description,
            is_active=data.is_active,
            updated_by_id=actor_id,
        )
        self.db.add(config)
        self.db.flush()

        self.audit.log(
            action="SYSTEM_CONFIG_CREATE",
            resource_type="SYSTEM_CONFIG",
            resource_id=str(config.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={"key": config.key, "type": config.value_type.value},
        )
        logger.info(f"Created SystemConfig '{config.key}' (id={config.id})")
        return config

    def get_config_by_key(self, key: str) -> SystemConfig:
        config = self.db.scalar(
            select(SystemConfig)
            .where(SystemConfig.key == key)
            .options(selectinload(SystemConfig.updated_by))
        )
        if not config:
            raise EntityNotFoundException(f"System configuration key '{key}' not found")
        return config

    def get_config_by_id(self, config_id: UUID) -> SystemConfig:
        config = self.db.scalar(
            select(SystemConfig)
            .where(SystemConfig.id == config_id)
            .options(selectinload(SystemConfig.updated_by))
        )
        if not config:
            raise EntityNotFoundException(f"System configuration '{config_id}' not found")
        return config

    def list_configs(self, is_active: Optional[bool] = None) -> List[SystemConfig]:
        stmt = select(SystemConfig).options(selectinload(SystemConfig.updated_by))
        if is_active is not None:
            stmt = stmt.where(SystemConfig.is_active == is_active)
        return list(self.db.scalars(stmt.order_by(SystemConfig.key.asc())).all())

    def update_config(self, key: str, data: SystemConfigUpdate, actor_id: UUID) -> SystemConfig:
        config = self.get_config_by_key(key)
        old_val = config.value

        clean_val = self.validate_typed_value(data.value, config.value_type)
        config.value = clean_val
        if data.description is not None:
            config.description = data.description
        if data.is_active is not None:
            config.is_active = data.is_active

        config.updated_by_id = actor_id
        config.updated_at = datetime.now(timezone.utc)

        self.audit.log(
            action="SYSTEM_CONFIG_UPDATE",
            resource_type="SYSTEM_CONFIG",
            resource_id=str(config.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={"key": config.key, "old_value": old_val, "new_value": clean_val},
        )
        return config
