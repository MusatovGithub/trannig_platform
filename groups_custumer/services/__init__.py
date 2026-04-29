"""
Сервисный слой для работы с группами и расписаниями.
"""

from .attendance_service import (
    ATTENDED_STATUSES,
    VALID_STATUSES,
    AttendanceBlockedError,
    AttendanceValidationError,
    create_payment_record,
    delete_payment_record,
    find_and_use_subscription,
    get_attendance_css_class,
    get_attendance_display_text,
    process_attendance_mark,
    return_subscription_usage,
    update_customer_balance,
    validate_attendance_status,
)
from .exceptions import (
    DateParseError,
    GroupPermissionError,
    GroupValidationError,
    ScheduleValidationError,
)
from .group_service import assign_coaches, create_group, update_group
from .schedule_service import (
    create_attendance_records_bulk,
    create_group_classes_bulk,
    create_schedules_bulk,
    delete_old_schedule_and_classes,
    generate_group_classes,
    preserve_attendance_data,
    restore_attendance_data,
)
from .validators import (
    parse_date_field,
    validate_end_date,
    validate_group_data,
    validate_schedule_data,
)

__all__ = [
    # Exceptions
    "GroupValidationError",
    "ScheduleValidationError",
    "GroupPermissionError",
    "DateParseError",
    "AttendanceValidationError",
    "AttendanceBlockedError",
    # Group Service
    "create_group",
    "update_group",
    "assign_coaches",
    # Schedule Service
    "create_schedules_bulk",
    "generate_group_classes",
    "create_group_classes_bulk",
    "create_attendance_records_bulk",
    "preserve_attendance_data",
    "restore_attendance_data",
    "delete_old_schedule_and_classes",
    # Attendance Service
    "process_attendance_mark",
    "validate_attendance_status",
    "update_customer_balance",
    "find_and_use_subscription",
    "create_payment_record",
    "return_subscription_usage",
    "delete_payment_record",
    "get_attendance_display_text",
    "get_attendance_css_class",
    "ATTENDED_STATUSES",
    "VALID_STATUSES",
    # Validators
    "validate_group_data",
    "validate_schedule_data",
    "parse_date_field",
    "validate_end_date",
]
