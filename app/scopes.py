from enum import StrEnum


class PropertyScope(StrEnum):
    READ = "properties:read"
    ME = "properties:me"
    WRITE = "properties:write"
    DELETE = "properties:delete"
    IMAGES = "properties:images"
    SCHEDULE = "properties:schedule"

    ADMIN = "admin:properties"
    ADMIN_READ = "admin:properties:read"
    ADMIN_WRITE = "admin:properties:write"
    ADMIN_DELETE = "admin:properties:delete"


PROPERTY_SCOPE_DESCRIPTIONS: dict[str, str] = {
    PropertyScope.READ: "Browse and search public property listings.",
    PropertyScope.ME: "Read your own properties and their details.",
    PropertyScope.WRITE: "Create and update your own properties (including translations).",
    PropertyScope.DELETE: "Delete your own properties.",
    PropertyScope.IMAGES: "Upload and manage images for your own properties.",
    PropertyScope.SCHEDULE: "Manage unavailability windows for your own properties.",
    PropertyScope.ADMIN_READ: "Read any property regardless of status (admin).",
    PropertyScope.ADMIN_WRITE: "Edit any property and change its status (admin).",
    PropertyScope.ADMIN_DELETE: "Hard-delete any property (admin).",
}
