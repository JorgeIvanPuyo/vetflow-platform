import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator


InventoryCategory = Literal["medication", "vaccine", "supply", "food", "accessory", "other"]
InventoryUnit = Literal[
    "unit",
    "tablet",
    "capsule",
    "ampoule",
    "dose",
    "pipette",
    "bottle",
    "vial",
    "syringe",
    "ml",
    "liter",
    "gram",
    "kg",
    "pair",
    "box",
    "package",
    "other",
]
InventoryStatusFilter = Literal[
    "low_stock",
    "expiring_soon",
    "expired",
    "active",
    "inactive",
]
InventoryStockStatus = Literal["in_stock", "low_stock", "out_of_stock", "negative"]
InventorySortBy = Literal[
    "name",
    "internal_code",
    "current_stock",
    "sale_price_ars",
    "updated_at",
]
SortOrder = Literal["asc", "desc"]
InventoryMovementType = Literal[
    "initial_stock",
    "manual_entry",
    "manual_exit",
    "purchase",
    "sale",
    "clinical_consumption",
    "customer_return",
    "supplier_return",
    "purchase_return",
    "adjustment_in",
    "adjustment_out",
    "expiration",
    "loss",
    "breakage",
    "transfer_in",
    "transfer_out",
    "reversal",
    "entry",
    "exit",
    "adjustment",
]
InventoryReversalStatus = Literal["all", "active", "reversed", "reversal"]
InventoryImportMode = Literal["initial_load", "catalog_update"]
InventoryExportMode = Literal["all", "filtered", "selected"]
InventoryBulkOperationType = Literal[
    "increase_sale_price_percentage",
    "decrease_sale_price_percentage",
    "set_profit_margin_percentage",
    "set_sale_price",
    "set_brand",
    "set_supplier",
    "set_minimum_stock",
    "activate",
    "deactivate",
]
InventoryBulkSelectionMode = Literal["selected", "filtered"]
InventoryBulkOperationStatus = Literal[
    "preview",
    "confirmed",
    "partially_reversed",
    "reversed",
    "failed",
    "expired",
]
InventoryBulkOperationItemStatus = Literal[
    "pending",
    "changed",
    "unchanged",
    "invalid",
    "conflict",
    "reverted",
    "excluded",
]
InventoryImportStatus = Literal["preview", "confirmed", "failed", "expired"]
InventoryImportRowStatus = Literal["valid", "warning", "error", "skipped"]
InventoryImportRowAction = Literal["create", "update", "skip", "review_required"]
InventoryImportMatchType = Literal[
    "exact_match",
    "possible_match",
    "new_product",
    "duplicate_in_file",
    "conflict",
    "invalid",
]
InventoryExitReason = Literal[
    "sale",
    "consultation_use",
    "inventory_adjustment",
    "expired_discard",
    "damaged",
    "other",
]


class InventoryItemWriteBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    category: InventoryCategory
    subcategory: str | None = Field(default=None, max_length=100)
    brand: str | None = Field(default=None, max_length=150)
    unit: InventoryUnit
    supplier: str | None = Field(default=None, max_length=255)
    lot_number: str | None = Field(default=None, max_length=120)
    expiration_date: date | None = None
    minimum_stock: Decimal = Field(default=Decimal("0"), ge=0)
    purchase_price_ars: Decimal | None = Field(default=None, ge=0)
    purchase_tax_rate_percentage: Decimal = Field(
        default=Decimal("21"),
        ge=0,
        le=100,
    )
    profit_margin_percentage: Decimal = Field(default=Decimal("35"), ge=0)
    sale_price_ars: Decimal | None = Field(default=None, ge=0)
    sale_tax_rate_percentage: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        le=100,
    )
    round_sale_price: bool = False
    notes: str | None = None
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def strip_required_string(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("String should have at least 1 character")
        return value

    @field_validator("subcategory", "brand", "supplier", "lot_number", "notes", mode="before")
    @classmethod
    def strip_optional_string(cls, value):
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        value = value.strip()
        return value or None


class InventoryItemCreate(InventoryItemWriteBase):
    pass


class InventoryItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    category: InventoryCategory | None = None
    subcategory: str | None = Field(default=None, max_length=100)
    brand: str | None = Field(default=None, max_length=150)
    unit: InventoryUnit | None = None
    supplier: str | None = Field(default=None, max_length=255)
    lot_number: str | None = Field(default=None, max_length=120)
    expiration_date: date | None = None
    minimum_stock: Decimal | None = Field(default=None, ge=0)
    purchase_price_ars: Decimal | None = Field(default=None, ge=0)
    purchase_tax_rate_percentage: Decimal | None = Field(default=None, ge=0, le=100)
    profit_margin_percentage: Decimal | None = Field(default=None, ge=0)
    sale_price_ars: Decimal | None = Field(default=None, ge=0)
    sale_tax_rate_percentage: Decimal | None = Field(default=None, ge=0, le=100)
    round_sale_price: bool | None = None
    notes: str | None = None
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def strip_optional_required_string(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("String should have at least 1 character")
        return value

    @field_validator("subcategory", "brand", "supplier", "lot_number", "notes", mode="before")
    @classmethod
    def strip_optional_string(cls, value):
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        value = value.strip()
        return value or None


class InventoryItemRead(InventoryItemWriteBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    internal_code: str
    current_stock: Decimal
    created_by_user_id: uuid.UUID | None = None
    purchase_tax_amount_ars: Decimal | None = None
    purchase_price_with_tax_ars: Decimal | None = None
    sale_tax_amount_ars: Decimal | None = None
    sale_price_with_tax_ars: Decimal | None = None
    is_low_stock: bool
    is_expiring_soon: bool
    is_expired: bool
    created_by_user_name: str | None = None
    created_by_user_email: str | None = None
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_by_user_id")
    def serialize_created_by_user_id(
        self,
        value: uuid.UUID | None,
    ) -> uuid.UUID | None:
        if self.created_by_user_name or self.created_by_user_email:
            return value
        return None


class InventorySummaryRead(BaseModel):
    total_items: int
    low_stock_count: int
    expiring_soon_count: int
    expired_count: int


class InventoryFilterOptionsRead(BaseModel):
    brands: list[str]
    suppliers: list[str]


class InventoryMovementEntryCreate(BaseModel):
    quantity: Decimal = Field(gt=0)
    total_cost_ars: Decimal | None = Field(default=None, ge=0)
    unit_cost_ars: Decimal | None = Field(default=None, ge=0)
    supplier: str | None = None
    notes: str | None = None


class InventoryMovementExitCreate(BaseModel):
    quantity: Decimal = Field(gt=0)
    reason: InventoryExitReason = "other"
    unit_sale_price_ars: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None
    related_patient_id: uuid.UUID | None = None
    related_consultation_id: uuid.UUID | None = None


class InventoryMovementReverseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=50)
    notes: str | None = None

    @field_validator("reason")
    @classmethod
    def strip_required_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("String should have at least 1 character")
        return value

    @field_validator("notes", mode="before")
    @classmethod
    def strip_optional_notes(cls, value):
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        value = value.strip()
        return value or None


class InventoryMovementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    inventory_item_id: uuid.UUID
    inventory_item_name: str | None = None
    inventory_item_internal_code: str | None = None
    movement_type: InventoryMovementType
    reason: str | None = None
    quantity: Decimal
    unit: str | None = None
    stock_before: Decimal | None = None
    stock_after: Decimal | None = None
    source_type: str | None = None
    source_id: str | None = None
    operation_id: uuid.UUID | None = None
    reverses_movement_id: uuid.UUID | None = None
    reversed_by_movement_id: uuid.UUID | None = None
    reversal_status: InventoryReversalStatus
    unit_cost_ars: Decimal | None = None
    total_cost_ars: Decimal | None = None
    unit_sale_price_ars: Decimal | None = None
    total_sale_price_ars: Decimal | None = None
    supplier: str | None = None
    notes: str | None = None
    related_patient_id: uuid.UUID | None = None
    related_consultation_id: uuid.UUID | None = None
    created_by_user_id: uuid.UUID | None = None
    created_by_user_name: str | None = None
    created_by_user_email: str | None = None
    created_at: datetime

    @field_serializer("created_by_user_id")
    def serialize_created_by_user_id(
        self,
        value: uuid.UUID | None,
    ) -> uuid.UUID | None:
        if self.created_by_user_name or self.created_by_user_email:
            return value
        return None


class InventoryMovementDetailRead(InventoryMovementRead):
    can_be_reversed: bool
    reversal_block_reason: str | None = None


class InventoryImportSummaryRead(BaseModel):
    row_count: int
    valid_count: int
    warning_count: int
    error_count: int
    create_count: int = 0
    update_count: int = 0
    skip_count: int = 0
    movement_count: int = 0
    stock_increase_total: Decimal = Decimal("0")
    stock_decrease_total: Decimal = Decimal("0")
    warnings: list[str] = Field(default_factory=list)


class InventoryImportRowRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    row_number: int
    normalized_data: dict
    existing_inventory_item_id: uuid.UUID | None = None
    match_type: InventoryImportMatchType
    proposed_action: InventoryImportRowAction
    status: InventoryImportRowStatus
    errors: list[str]
    warnings: list[str]
    product_snapshot: dict | None = None
    changed_fields: list[str]
    stock_current: Decimal | None = None
    stock_target: Decimal | None = None
    stock_delta: Decimal | None = None
    expected_movement_type: str | None = None


class InventoryImportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    mode: InventoryImportMode
    status: InventoryImportStatus
    original_filename: str
    file_hash: str
    row_count: int
    valid_count: int
    warning_count: int
    error_count: int
    operation_id: uuid.UUID | None = None
    result_summary: dict | None = None
    expires_at: datetime
    confirmed_at: datetime | None = None
    created_by_user_id: uuid.UUID | None = None
    created_by_user_name: str | None = None
    created_by_user_email: str | None = None
    created_at: datetime
    rows: list[InventoryImportRowRead] = Field(default_factory=list)
    summary: InventoryImportSummaryRead | None = None

    @field_serializer("created_by_user_id")
    def serialize_import_created_by_user_id(
        self,
        value: uuid.UUID | None,
    ) -> uuid.UUID | None:
        if self.created_by_user_name or self.created_by_user_email:
            return value
        return None


class InventoryImportListItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    mode: InventoryImportMode
    status: InventoryImportStatus
    original_filename: str
    row_count: int
    valid_count: int
    warning_count: int
    error_count: int
    operation_id: uuid.UUID | None = None
    expires_at: datetime
    confirmed_at: datetime | None = None
    created_by_user_name: str | None = None
    created_by_user_email: str | None = None
    created_at: datetime


class InventoryImportConfirmRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    row_id: uuid.UUID
    selected: bool = True
    action: InventoryImportRowAction


class InventoryImportConfirmCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    explicit_confirm: bool
    rows: list[InventoryImportConfirmRow] = Field(default_factory=list)
    reason: str | None = Field(default=None, max_length=120)

    @field_validator("reason", mode="before")
    @classmethod
    def strip_import_reason(cls, value):
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        value = value.strip()
        return value or None


class InventoryExportFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    search: str | None = Field(default=None, max_length=255)
    category: InventoryCategory | None = None
    brand: str | None = Field(default=None, max_length=150)
    supplier: str | None = Field(default=None, max_length=255)
    stock_status: InventoryStockStatus | None = None
    is_active: bool | None = None
    sort_by: InventorySortBy | None = None
    sort_direction: SortOrder | None = None

    @field_validator("search", "brand", "supplier", mode="before")
    @classmethod
    def strip_export_filter_string(cls, value):
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        value = value.strip()
        return value or None

    def has_filters_except_active(self) -> bool:
        return any(
            getattr(self, field) is not None
            for field in (
                "search",
                "category",
                "brand",
                "supplier",
                "stock_status",
                "sort_by",
                "sort_direction",
            )
        )

    def has_any_filter(self) -> bool:
        return any(
            getattr(self, field) is not None
            for field in (
                "search",
                "category",
                "brand",
                "supplier",
                "stock_status",
                "is_active",
                "sort_by",
                "sort_direction",
            )
        )


class InventoryExportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: InventoryExportMode
    filters: InventoryExportFilters | None = None
    selected_ids: list[uuid.UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_export_combination(self):
        filters = self.filters
        if self.mode == "all":
            if filters is not None and filters.has_filters_except_active():
                raise ValueError("all mode only accepts filters.is_active")
            return self
        if self.mode == "filtered":
            if self.selected_ids:
                raise ValueError("filtered mode does not accept selected_ids")
            return self
        if not self.selected_ids:
            raise ValueError("selected mode requires selected_ids")
        if len(self.selected_ids) > 500:
            raise ValueError("selected mode accepts at most 500 selected_ids")
        if filters is not None and filters.has_any_filter():
            raise ValueError("selected mode does not accept filters")
        return self


class InventoryBulkOperationFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    search: str | None = Field(default=None, max_length=255)
    category: InventoryCategory | None = None
    brand: str | None = Field(default=None, max_length=150)
    supplier: str | None = Field(default=None, max_length=255)
    stock_status: InventoryStockStatus | None = None
    is_active: bool | None = None

    @field_validator("search", "brand", "supplier", mode="before")
    @classmethod
    def strip_bulk_filter_string(cls, value):
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        value = value.strip()
        return value or None


class InventoryBulkSelectionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selection_mode: InventoryBulkSelectionMode
    selected_ids: list[uuid.UUID] = Field(default_factory=list)
    filters: InventoryBulkOperationFilters | None = None
    excluded_ids: list[uuid.UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_bulk_selection(self):
        if len(self.selected_ids) > 500:
            raise ValueError("selected_ids accepts at most 500 ids")
        if len(self.excluded_ids) > 500:
            raise ValueError("excluded_ids accepts at most 500 ids")
        if self.selection_mode == "selected":
            if not self.selected_ids:
                raise ValueError("selected mode requires selected_ids")
            if self.filters is not None:
                raise ValueError("selected mode does not accept filters")
        elif self.selected_ids:
            raise ValueError("filtered mode does not accept selected_ids")
        return self


class InventoryBulkOperationValueCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_type: InventoryBulkOperationType
    percentage: Decimal | None = Field(default=None, gt=0, le=1000)
    sale_price_ars: Decimal | None = Field(default=None, ge=0)
    profit_margin_percentage: Decimal | None = Field(default=None, ge=0, le=1000)
    brand: str | None = Field(default=None, max_length=150)
    supplier: str | None = Field(default=None, max_length=255)
    minimum_stock: Decimal | None = Field(default=None, ge=0)
    confirm_clear: bool = False

    @field_validator("brand", "supplier", mode="before")
    @classmethod
    def strip_bulk_value_string(cls, value):
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        return value.strip()

    @model_validator(mode="after")
    def validate_bulk_value(self):
        if self.operation_type in {
            "increase_sale_price_percentage",
            "decrease_sale_price_percentage",
        }:
            if self.percentage is None:
                raise ValueError("percentage is required")
        elif self.operation_type == "set_profit_margin_percentage":
            if self.profit_margin_percentage is None:
                raise ValueError("profit_margin_percentage is required")
        elif self.operation_type == "set_sale_price":
            if self.sale_price_ars is None:
                raise ValueError("sale_price_ars is required")
        elif self.operation_type == "set_brand":
            if self.brand is None:
                raise ValueError("brand is required")
            if self.brand == "" and not self.confirm_clear:
                raise ValueError("confirm_clear is required to clear brand")
        elif self.operation_type == "set_supplier":
            if self.supplier is None:
                raise ValueError("supplier is required")
            if self.supplier == "" and not self.confirm_clear:
                raise ValueError("confirm_clear is required to clear supplier")
        elif self.operation_type == "set_minimum_stock":
            if self.minimum_stock is None:
                raise ValueError("minimum_stock is required")
        return self


class InventoryBulkOperationPreviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selection: InventoryBulkSelectionCreate
    operation: InventoryBulkOperationValueCreate


class InventoryBulkOperationConfirmCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm: bool

    @model_validator(mode="after")
    def validate_confirm(self):
        if not self.confirm:
            raise ValueError("confirm must be true")
        return self


class InventoryBulkOperationReverseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=255)

    @field_validator("reason")
    @classmethod
    def strip_reverse_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("String should have at least 1 character")
        return value


class InventoryBulkOperationSummaryRead(BaseModel):
    selected_count: int
    affected_count: int
    unchanged_count: int
    invalid_count: int
    excluded_count: int
    reversed_count: int
    conflict_count: int


class InventoryBulkOperationItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    inventory_item_id: uuid.UUID
    inventory_item_name: str | None = None
    inventory_item_internal_code: str | None = None
    field_name: str
    old_value_json: dict | None = None
    new_value_json: dict | None = None
    product_updated_at_snapshot: datetime
    status: InventoryBulkOperationItemStatus
    error_message: str | None = None
    reverted_at: datetime | None = None
    created_at: datetime


class InventoryBulkOperationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    operation_type: InventoryBulkOperationType
    selection_mode: InventoryBulkSelectionMode
    filters_json: dict | None = None
    request_json: dict
    status: InventoryBulkOperationStatus
    selected_count: int
    affected_count: int
    unchanged_count: int
    invalid_count: int
    excluded_count: int
    reversed_count: int
    conflict_count: int
    expires_at: datetime
    confirmed_at: datetime | None = None
    reversed_at: datetime | None = None
    reversed_by_user_id: uuid.UUID | None = None
    reversed_by_user_name: str | None = None
    reversed_by_user_email: str | None = None
    reversal_reason: str | None = None
    created_by_user_id: uuid.UUID | None = None
    created_by_user_name: str | None = None
    created_by_user_email: str | None = None
    created_at: datetime
    items: list[InventoryBulkOperationItemRead] = Field(default_factory=list)
    summary: InventoryBulkOperationSummaryRead | None = None

    @field_serializer("created_by_user_id")
    def serialize_bulk_created_by_user_id(
        self,
        value: uuid.UUID | None,
    ) -> uuid.UUID | None:
        if self.created_by_user_name or self.created_by_user_email:
            return value
        return None

    @field_serializer("reversed_by_user_id")
    def serialize_bulk_reversed_by_user_id(
        self,
        value: uuid.UUID | None,
    ) -> uuid.UUID | None:
        if self.reversed_by_user_name or self.reversed_by_user_email:
            return value
        return None


class InventoryBulkOperationListItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    operation_type: InventoryBulkOperationType
    selection_mode: InventoryBulkSelectionMode
    status: InventoryBulkOperationStatus
    selected_count: int
    affected_count: int
    unchanged_count: int
    invalid_count: int
    excluded_count: int
    reversed_count: int
    conflict_count: int
    confirmed_at: datetime | None = None
    reversed_at: datetime | None = None
    reversed_by_user_name: str | None = None
    reversed_by_user_email: str | None = None
    created_by_user_name: str | None = None
    created_by_user_email: str | None = None
    created_at: datetime


InventoryDashboardAlertType = Literal[
    "negative_stock",
    "out_of_stock",
    "low_stock",
    "inactive_with_stock",
    "missing_purchase_cost",
    "missing_sale_price",
    "missing_brand",
    "missing_supplier",
]
InventoryDashboardAlertPriority = Literal["critical", "high", "medium", "info"]


class InventoryDashboardAppliedFiltersRead(BaseModel):
    category: InventoryCategory | None = None
    brand: str | None = None
    supplier: str | None = None
    is_active: bool | None = None
    date_from: date
    date_to: date


class InventoryDashboardIndicatorsRead(BaseModel):
    total_products: int
    active_products: int
    inactive_products: int
    in_stock_products: int
    low_stock_products: int
    out_of_stock_products: int
    negative_stock_products: int


class InventoryDashboardValuationRead(BaseModel):
    estimated_cost_value_ars: Decimal
    estimated_sale_value_ars: Decimal
    includes_negative_stock: bool
    disclaimer: str


class InventoryDashboardMovementMetricsRead(BaseModel):
    total_movements: int
    entry_movements: int
    exit_movements: int
    adjustment_movements: int
    reversal_movements: int
    clinical_consumption_movements: int


class InventoryDashboardAlertRead(BaseModel):
    alert_type: InventoryDashboardAlertType
    priority: InventoryDashboardAlertPriority
    count: int
    label: str


class InventoryDashboardAttentionItemRead(BaseModel):
    id: uuid.UUID
    internal_code: str
    name: str
    category: InventoryCategory
    current_stock: Decimal
    minimum_stock: Decimal
    sale_price_ars: Decimal | None = None
    alerts: list[InventoryDashboardAlertType]
    priority: InventoryDashboardAlertPriority


class InventoryDashboardActivityRead(BaseModel):
    recent_movements: list[InventoryMovementRead]
    recent_imports: list[InventoryImportListItemRead]
    recent_bulk_operations: list[InventoryBulkOperationListItemRead]


class InventoryDashboardRead(BaseModel):
    generated_at: datetime
    filters: InventoryDashboardAppliedFiltersRead
    indicators: InventoryDashboardIndicatorsRead
    valuation: InventoryDashboardValuationRead
    movement_metrics: InventoryDashboardMovementMetricsRead
    alerts: list[InventoryDashboardAlertRead]
    attention_items: list[InventoryDashboardAttentionItemRead]
    activity: InventoryDashboardActivityRead
