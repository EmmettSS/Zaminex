from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers


class AttributeValuesMixin:
    attribute_value_model = None
    attribute_owner_field = None
    attribute_entity = None

    @staticmethod
    def _attribute_values(obj):
        cache = getattr(obj, "_prefetched_objects_cache", None)
        if cache is not None and "attribute_values" in cache:
            return sorted(
                cache["attribute_values"],
                key=lambda value: value.attribute.sort_order,
            )
        return list(
            obj.attribute_values.select_related("attribute").order_by(
                "attribute__sort_order"
            )
        )

    def get_attributes(self, obj) -> dict:
        return {
            value.attribute.name: value.value
            for value in self._attribute_values(obj)
        }

    def get_attributeDetails(self, obj) -> list:
        details = []
        for value in self._attribute_values(obj):
            attribute = value.attribute
            details.append(
                {
                    "name": attribute.name,
                    "displayName": attribute.display_name,
                    "dataType": attribute.data_type,
                    "unit": attribute.unit,
                    "isFacility": attribute.is_facility,
                    "value": value.value,
                    "displayValue": value.display_value,
                }
            )
        return details

    def _pop_attribute_payload(self):
        request = self.context.get("request")
        if request is None:
            return None
        payload = request.data.get("attributes")
        if payload in (None, ""):
            return None
        if not isinstance(payload, dict):
            raise serializers.ValidationError(
                {"attributes": "قالب ویژگی‌ها نامعتبر است؛ یک شیء کلید/مقدار انتظار می‌رود."}
            )
        return payload

    def _save_attribute_values(self, instance, payload: dict):
        from apps.basics.models import Attribute

        if not payload:
            return

        names = list(payload.keys())
        attributes = {
            attribute.name: attribute
            for attribute in Attribute.objects.filter(
                name__in=names, entity=self.attribute_entity
            ).prefetch_related("options")
        }

        unknown = [name for name in names if name not in attributes]
        if unknown:
            raise serializers.ValidationError(
                {"attributes": f"ویژگی‌های ناشناخته: {'، '.join(unknown)}"}
            )

        core = [name for name, attr in attributes.items() if attr.is_core]
        if core:
            raise serializers.ValidationError(
                {
                    "attributes": (
                        f"ویژگی‌های ثابت باید در فیلد اصلی خود ارسال شوند: {'، '.join(core)}"
                    )
                }
            )

        errors: dict[str, str] = {}
        for name, raw in payload.items():
            attribute = attributes[name]
            owner = {self.attribute_owner_field: instance}

            if raw is None or raw == "":
                self.attribute_value_model.objects.filter(
                    attribute=attribute, **owner
                ).delete()
                continue

            value = self.attribute_value_model.objects.filter(
                attribute=attribute, **owner
            ).first()
            if value is None:
                value = self.attribute_value_model(attribute=attribute, **owner)

            try:
                value.set_value(raw)
            except DjangoValidationError as exc:
                message = exc.message_dict.get(name) if hasattr(exc, "message_dict") else None
                errors[name] = message[0] if message else str(exc.messages[0])
                continue

            value.save()

        if errors:
            raise serializers.ValidationError({"attributes": errors})

    def _validate_required_attributes(self, instance, type_obj, link_manager_name):
        if type_obj is None:
            return

        links = getattr(type_obj, link_manager_name).filter(
            is_active=True, is_required=True, attribute__is_active=True
        ).select_related("attribute")

        missing = []
        for link in links:
            attribute = link.attribute
            if attribute.is_core:
                continue
            owner = {self.attribute_owner_field: instance}
            exists = self.attribute_value_model.objects.filter(
                attribute=attribute, **owner
            ).exists()
            if not exists:
                missing.append(attribute.display_name)

        if missing:
            raise serializers.ValidationError(
                {"attributes": f"این ویژگی‌ها الزامی هستند: {'، '.join(missing)}"}
            )
