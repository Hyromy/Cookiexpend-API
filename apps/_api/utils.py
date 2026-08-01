from typing import Any, Literal

from .models import BaseModel


class MassiveHandler:
    def __init__(self, sheets_count: int = 1):
        self._reply = self._empty_reply(sheets_count)

    def _empty_reply(self, sheets_count: int = 1):
        return {
            "errors": [{} for _ in range(sheets_count)],
            "duplicated": [{} for _ in range(sheets_count)],
            "inserted": [{} for _ in range(sheets_count)],
        }

    def reset_reply(self, sheets_count: int = 1):
        self._reply = self._empty_reply(sheets_count)

    @property
    def reply(self):
        return self._reply

    @staticmethod
    def _find_by_arg(
        *, current_item, col_name: str, model: BaseModel, filter_by: str = "pk"
    ) -> BaseModel | None | Literal[False]:
        if current_item.get(col_name):
            found_item = model.objects.filter(**{filter_by: current_item[col_name]})
            return found_item.first() if found_item.exists() else None
        return False

    def set(
        self,
        *,
        slot: Literal["errors", "duplicated", "inserted"],
        sheet_index: int,
        obj_index: int,
        value: str,
    ):
        """Record a string message in the specified slot list for the given object index."""
        sheet_slot = self._reply[slot][sheet_index]
        key = str(obj_index)

        if key not in sheet_slot:
            sheet_slot[key] = []

        sheet_slot[key].append(value)

    def fk_value_handler(
        self,
        *,
        current_item,
        col_name: str,
        model: BaseModel,
        sheet_index: int,
        obj_index: int,
        filter_by: str = "pk",
    ) -> bool:
        found = MassiveHandler._find_by_arg(
            current_item=current_item, col_name=col_name, model=model, filter_by=filter_by
        )
        if isinstance(found, model):
            current_item[col_name] = found.id
            return False
        elif found is None:
            error_msg = f"{col_name}: '{current_item.get(col_name, 'N/A')}' not found"
            self.set(slot="errors", sheet_index=sheet_index, obj_index=obj_index, value=error_msg)
            return True

        return False

    def validation_err_handler(
        self, e: Exception, /, *, sheet_index: int, current_obj: Any, obj_index: int
    ):
        errors_dict = getattr(e, "detail", {})

        is_duplicate = any(
            getattr(error_detail, "code", "") == "unique"
            for errors in errors_dict.values()
            for error_detail in (errors if isinstance(errors, list) else [errors])
        )

        slot = "duplicated" if is_duplicate else "errors"

        for field, messages in errors_dict.items():
            if not isinstance(messages, list):
                messages = [messages]

            for msg in messages:
                error_msg = (
                    f"{field}: '{current_obj.get(field, 'N/A')}' {msg}"
                    if field != "non_field_errors"
                    else str(msg)
                )
                self.set(slot=slot, sheet_index=sheet_index, obj_index=obj_index, value=error_msg)

    def unknown_err_handler(self, e: Exception, /, *, sheet_index: int, obj_index: int):
        self.set(
            slot="errors",
            sheet_index=sheet_index,
            obj_index=obj_index,
            value=f"Exception: {str(e)}",
        )
