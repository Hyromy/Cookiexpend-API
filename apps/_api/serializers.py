def auditory_fields(*args: str) -> list[str]:
    """Helper function to generate basic fields for serializers, including id, created_at, updated_at, and version."""

    return ["id"] + list(args) + ["created_at", "updated_at", "version"]
