"""Serializers for the reference-data API.

Two shapes are exposed:

* **management** serializers — full CRUD for the "اطلاعات پایه" admin screens.
* **form-schema** serializers — the compact payload the property/listing forms
  consume to render themselves (:class:`FormSchemaSerializer`).

Field names stay ``camelCase`` on the wire to match the conventions already
used by the existing endpoints.
"""

from __future__ import annotations

from rest_framework import serializers

from .models import (
    Attribute,
    AttributeOption,
    DealType,
    DealTypeAttribute,
    DealTypeSearchAttribute,
    City,
    District,
    Province,
    PropertyType,
    PropertyTypeAttribute,
    PropertyTypeSearchAttribute,
    PropertyUsage,
)


# ---------------------------------------------------------------------------
#  Attribute options
# ---------------------------------------------------------------------------

class AttributeOptionSerializer(serializers.ModelSerializer):
    displayName = serializers.CharField(source="display_name")
    sortOrder = serializers.DecimalField(
        source="sort_order", max_digits=10, decimal_places=2, required=False
    )
    isActive = serializers.BooleanField(source="is_active", required=False)
    value = serializers.CharField(required=False)

    class Meta:
        model = AttributeOption
        fields = ["id", "value", "displayName", "sortOrder", "isActive"]

    def validate(self, attrs):
        """Derive the stored key from the label, and keep labels unique.

        The management UI only asks for the Persian label; making the operator
        also invent an English key would be pointless friction. Two options
        with the same label are indistinguishable in a dropdown, so those are
        rejected even though their keys would differ.
        """
        from django.utils.text import slugify

        attribute = self.context.get("attribute") or getattr(
            self.instance, "attribute", None
        )
        label = (attrs.get("display_name") or "").strip()

        if attribute is not None and label:
            clash = AttributeOption.objects.filter(
                attribute=attribute, display_name=label
            )
            if self.instance is not None:
                clash = clash.exclude(pk=self.instance.pk)
            if clash.exists():
                raise serializers.ValidationError(
                    {"displayName": f"«{label}» قبلاً برای این ویژگی ثبت شده است."}
                )

        if attrs.get("value") or self.instance is not None:
            return attrs

        base = slugify(label, allow_unicode=True) or "option"
        candidate, suffix = base, 1
        if attribute is not None:
            while AttributeOption.all_objects.filter(
                attribute=attribute, value=candidate
            ).exists():
                suffix += 1
                candidate = f"{base}-{suffix}"
        attrs["value"] = candidate
        return attrs


# ---------------------------------------------------------------------------
#  Attributes
# ---------------------------------------------------------------------------

class AttributeSerializer(serializers.ModelSerializer):
    """Full attribute representation used by the management screens."""

    displayName = serializers.CharField(source="display_name")
    dataType = serializers.ChoiceField(source="data_type", choices=Attribute.DataType.choices)
    inputType = serializers.ChoiceField(
        source="input_type", choices=Attribute.InputType.choices, required=False
    )
    filterType = serializers.ChoiceField(
        source="filter_type", choices=Attribute.FilterType.choices, required=False
    )
    isFacility = serializers.BooleanField(source="is_facility", required=False)
    isCore = serializers.BooleanField(source="is_core", read_only=True)
    coreField = serializers.CharField(source="core_field", read_only=True)
    sortOrder = serializers.DecimalField(
        source="sort_order", max_digits=10, decimal_places=2, required=False
    )
    isActive = serializers.BooleanField(source="is_active", required=False)
    options = AttributeOptionSerializer(many=True, read_only=True)
    usageCount = serializers.SerializerMethodField()
    # Optional on create: derived from the Persian label, the same way the
    # geography endpoints do it.
    name = serializers.CharField(required=False)

    class Meta:
        model = Attribute
        fields = [
            "id", "name", "displayName", "dataType", "inputType", "filterType",
            "entity", "unit", "isFacility", "isCore", "coreField",
            "sortOrder", "isActive", "options", "usageCount",
        ]

    def get_usageCount(self, obj) -> int:
        """How many property/deal types reference this attribute.

        Surfaced so the UI can warn before deactivating something in use.
        """
        return obj.property_types.count() + obj.deal_types.count()

    def validate_name(self, value):
        """`name` is a stable key: unique among live rows and immutable."""
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("کلید سیستمی نمی‌تواند خالی باشد.")

        if self.instance and self.instance.name != value:
            raise serializers.ValidationError(
                "کلید سیستمی پس از ایجاد قابل تغییر نیست؛ نام نمایشی را ویرایش کنید."
            )

        clash = Attribute.objects.filter(name=value)
        if self.instance:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError("این کلید سیستمی قبلاً ثبت شده است.")
        return value

    def validate(self, attrs):
        """Derive the key when omitted, then block edits that orphan data.

        Changing an attribute's data type would leave existing rows in the
        wrong typed column (an integer recorded in ``value_integer`` is
        invisible once the attribute claims to be text).
        """
        # Two attributes sharing a label are indistinguishable in the admin
        # list, so labels are unique too — not just the generated key.
        label = (attrs.get("display_name") or "").strip()
        if label:
            clash = Attribute.objects.filter(display_name=label)
            if self.instance:
                clash = clash.exclude(pk=self.instance.pk)
            if clash.exists():
                raise serializers.ValidationError(
                    {"displayName": f"ویژگی «{label}» قبلاً ثبت شده است."}
                )

        if attrs.get("is_facility"):
            attrs["data_type"] = Attribute.DataType.BOOLEAN

        # The model defaults to «بدون فیلتر». A newly created field should
        # still appear in list filters unless the operator *sent* none.
        if self.instance is None and "filter_type" not in attrs:
            data_type = attrs.get("data_type") or Attribute.DataType.TEXT
            attrs["filter_type"] = {
                Attribute.DataType.INTEGER: Attribute.FilterType.RANGE,
                Attribute.DataType.DECIMAL: Attribute.FilterType.RANGE,
                Attribute.DataType.DATE: Attribute.FilterType.RANGE,
                Attribute.DataType.BOOLEAN: Attribute.FilterType.EXISTS,
                Attribute.DataType.SELECT: Attribute.FilterType.EXACT,
                Attribute.DataType.MULTISELECT: Attribute.FilterType.EXACT,
                Attribute.DataType.TEXT: Attribute.FilterType.EXACT,
            }.get(data_type, Attribute.FilterType.EXACT)

        if self.instance is None and not attrs.get("name"):
            from django.utils.text import slugify

            base = slugify(label, allow_unicode=True) or "attribute"
            candidate, suffix = base, 1
            while Attribute.all_objects.filter(name=candidate).exists():
                suffix += 1
                candidate = f"{base}-{suffix}"
            attrs["name"] = candidate

        if self.instance and "data_type" in attrs:
            if attrs["data_type"] != self.instance.data_type:
                if self._has_stored_values(self.instance):
                    raise serializers.ValidationError(
                        {
                            "dataType": "برای این ویژگی مقدار ثبت شده است؛ "
                            "نوع داده قابل تغییر نیست."
                        }
                    )

        if self.instance and self.instance.is_core:
            protected = {"data_type", "entity"}
            changed = protected.intersection(attrs.keys())
            if any(getattr(self.instance, field) != attrs[field] for field in changed):
                raise serializers.ValidationError(
                    "ویژگی‌های ثابت به ستون‌های پایگاه داده متصل هستند و "
                    "نوع داده یا موجودیت آن‌ها قابل تغییر نیست."
                )
        return attrs

    @staticmethod
    def _has_stored_values(attribute) -> bool:
        from apps.listings.models import ListingAttributeValue
        from apps.properties.models import PropertyAttributeValue

        return (
            PropertyAttributeValue.objects.filter(attribute=attribute).exists()
            or ListingAttributeValue.objects.filter(attribute=attribute).exists()
        )


class AttributeMiniSerializer(serializers.ModelSerializer):
    """Compact attribute payload embedded in form schemas."""

    displayName = serializers.CharField(source="display_name")
    dataType = serializers.CharField(source="data_type")
    inputType = serializers.CharField(source="input_type")
    filterType = serializers.CharField(source="filter_type")
    isFacility = serializers.BooleanField(source="is_facility")
    isCore = serializers.BooleanField(source="is_core")
    coreField = serializers.CharField(source="core_field")
    options = serializers.SerializerMethodField()

    class Meta:
        model = Attribute
        fields = [
            "id", "name", "displayName", "dataType", "inputType", "filterType",
            "unit", "isFacility", "isCore", "coreField", "options",
        ]

    def get_options(self, obj):
        if obj.data_type not in {Attribute.DataType.SELECT, Attribute.DataType.MULTISELECT}:
            return []
        return [
            {"value": option.value, "displayName": option.display_name}
            for option in obj.options.filter(is_active=True)
        ]


# ---------------------------------------------------------------------------
#  Usages / types / deal types
# ---------------------------------------------------------------------------

class PropertyUsageSerializer(serializers.ModelSerializer):
    displayName = serializers.CharField(source="display_name")
    sortOrder = serializers.DecimalField(
        source="sort_order", max_digits=10, decimal_places=2, required=False
    )
    isActive = serializers.BooleanField(source="is_active", required=False)
    propertyTypeCount = serializers.SerializerMethodField()

    class Meta:
        model = PropertyUsage
        fields = ["id", "name", "displayName", "sortOrder", "isActive", "propertyTypeCount"]

    def get_propertyTypeCount(self, obj) -> int:
        return obj.property_types.count()


class PropertyTypeSerializer(serializers.ModelSerializer):
    displayName = serializers.CharField(source="display_name")
    propertyUsage = serializers.PrimaryKeyRelatedField(
        source="property_usage", queryset=PropertyUsage.objects.all()
    )
    propertyUsageName = serializers.CharField(
        source="property_usage.display_name", read_only=True
    )
    sortOrder = serializers.DecimalField(
        source="sort_order", max_digits=10, decimal_places=2, required=False
    )
    isActive = serializers.BooleanField(source="is_active", required=False)
    attributeCount = serializers.SerializerMethodField()
    propertyCount = serializers.SerializerMethodField()

    class Meta:
        model = PropertyType
        fields = [
            "id", "name", "displayName", "propertyUsage", "propertyUsageName",
            "slug", "sortOrder", "isActive", "attributeCount", "propertyCount",
        ]

    def get_attributeCount(self, obj) -> int:
        return obj.attribute_links.filter(is_active=True).count()

    def get_propertyCount(self, obj) -> int:
        """Existing properties of this type — the UI warns before deactivating."""
        return obj.properties.count()


class DealTypeSerializer(serializers.ModelSerializer):
    displayName = serializers.CharField(source="display_name")
    sortOrder = serializers.DecimalField(
        source="sort_order", max_digits=10, decimal_places=2, required=False
    )
    isActive = serializers.BooleanField(source="is_active", required=False)
    attributeCount = serializers.SerializerMethodField()
    listingCount = serializers.SerializerMethodField()

    class Meta:
        model = DealType
        fields = [
            "id", "name", "displayName", "sortOrder", "isActive",
            "attributeCount", "listingCount",
        ]

    def get_attributeCount(self, obj) -> int:
        return obj.attribute_links.filter(is_active=True).count()

    def get_listingCount(self, obj) -> int:
        return obj.listings.count()


# ---------------------------------------------------------------------------
#  Attribute bindings
# ---------------------------------------------------------------------------

class PropertyTypeAttributeSerializer(serializers.ModelSerializer):
    propertyType = serializers.PrimaryKeyRelatedField(
        source="property_type", queryset=PropertyType.objects.all()
    )
    attributeDetail = AttributeMiniSerializer(source="attribute", read_only=True)
    isRequired = serializers.BooleanField(source="is_required", required=False)
    sortOrder = serializers.DecimalField(
        source="sort_order", max_digits=10, decimal_places=2, required=False
    )
    isActive = serializers.BooleanField(source="is_active", required=False)

    class Meta:
        model = PropertyTypeAttribute
        fields = [
            "id", "propertyType", "attribute", "attributeDetail",
            "isRequired", "sortOrder", "isActive",
        ]

    def validate_attribute(self, value):
        if value.entity != Attribute.Entity.PROPERTY:
            raise serializers.ValidationError(
                "فقط ویژگی‌های مربوط به ملک را می‌توان به نوع ملک متصل کرد."
            )
        return value


class DealTypeAttributeSerializer(serializers.ModelSerializer):
    dealType = serializers.PrimaryKeyRelatedField(
        source="deal_type", queryset=DealType.objects.all()
    )
    attributeDetail = AttributeMiniSerializer(source="attribute", read_only=True)
    isRequired = serializers.BooleanField(source="is_required", required=False)
    sortOrder = serializers.DecimalField(
        source="sort_order", max_digits=10, decimal_places=2, required=False
    )
    isActive = serializers.BooleanField(source="is_active", required=False)

    class Meta:
        model = DealTypeAttribute
        fields = [
            "id", "dealType", "attribute", "attributeDetail",
            "isRequired", "sortOrder", "isActive",
        ]

    def validate_attribute(self, value):
        if value.entity != Attribute.Entity.LISTING:
            raise serializers.ValidationError(
                "فقط ویژگی‌های مربوط به آگهی را می‌توان به نوع معامله متصل کرد."
            )
        return value


# ---------------------------------------------------------------------------
#  Form schema — what the dynamic forms consume
# ---------------------------------------------------------------------------

class FormFieldSerializer(serializers.Serializer):
    """One field in a dynamically generated form.

    Built from a ``*TypeAttribute`` link so it carries both the attribute
    definition and the per-type overrides (required, ordering).
    """

    id = serializers.IntegerField(source="attribute.id")
    name = serializers.CharField(source="attribute.name")
    displayName = serializers.CharField(source="attribute.display_name")
    dataType = serializers.CharField(source="attribute.data_type")
    inputType = serializers.CharField(source="attribute.input_type")
    unit = serializers.CharField(source="attribute.unit")
    isFacility = serializers.BooleanField(source="attribute.is_facility")
    isCore = serializers.BooleanField(source="attribute.is_core")
    coreField = serializers.CharField(source="attribute.core_field")
    isRequired = serializers.BooleanField(source="is_required")
    sortOrder = serializers.DecimalField(
        source="sort_order", max_digits=10, decimal_places=2
    )
    options = serializers.SerializerMethodField()

    def get_options(self, obj):
        attribute = obj.attribute
        if attribute.data_type not in {
            Attribute.DataType.SELECT,
            Attribute.DataType.MULTISELECT,
        }:
            return []
        return [
            {"value": option.value, "displayName": option.display_name}
            for option in attribute.options.filter(is_active=True)
        ]


class SearchFilterSerializer(serializers.Serializer):
    """One filter in a dynamically generated search bar."""

    id = serializers.IntegerField(source="attribute.id")
    name = serializers.CharField(source="attribute.name")
    displayName = serializers.CharField(source="attribute.display_name")
    dataType = serializers.CharField(source="attribute.data_type")
    filterType = serializers.CharField(source="attribute.filter_type")
    unit = serializers.CharField(source="attribute.unit")
    isCore = serializers.BooleanField(source="attribute.is_core")
    coreField = serializers.CharField(source="attribute.core_field")
    sortOrder = serializers.DecimalField(
        source="sort_order", max_digits=10, decimal_places=2
    )
    options = serializers.SerializerMethodField()

    def get_options(self, obj):
        attribute = obj.attribute
        if attribute.data_type not in {
            Attribute.DataType.SELECT,
            Attribute.DataType.MULTISELECT,
        }:
            return []
        return [
            {"value": option.value, "displayName": option.display_name}
            for option in attribute.options.filter(is_active=True)
        ]


# ---------------------------------------------------------------------------
#  Geography
# ---------------------------------------------------------------------------

class SystemKeyFromLabelMixin:
    """Derive the system key (``name``) before per-field validation runs.

    The management UI only asks for the Persian label — inventing an English
    key is not something an operator should have to do. ``validate()`` is the
    natural place to fill it in, but it runs *after* every field has been
    validated: if ``name`` is ever treated as required, the request is already
    rejected with a bare "این مقدار لازم است." that names a field the form does
    not even show, and the autofill is never reached.

    Supplying the key here — in ``to_internal_value``, before field validation
    — makes the contract robust regardless of how ``name`` is declared, so the
    label the operator typed is always enough to create a row.
    """

    #: Model field that scopes uniqueness (``province`` for a city, ``city``
    #: for a district). ``None`` means the key is unique table-wide.
    system_key_scope: str | None = None

    def to_internal_value(self, data):
        # Only on create: an existing row keeps its key, which may already be
        # referenced elsewhere.
        if self.instance is None and not (data or {}).get("name"):
            label = (data or {}).get("displayName") or ""
            scope = {}
            scope_field = self.system_key_scope
            if scope_field:
                raw = (data or {}).get(scope_field)
                # Resolve the parent only when it is a usable id; an invalid or
                # missing parent is reported by the field itself, in Persian.
                if raw not in (None, ""):
                    model_field = self.fields.get(scope_field)
                    queryset = getattr(model_field, "queryset", None)
                    if queryset is not None:
                        parent = queryset.filter(pk=raw).first()
                        if parent is not None:
                            scope[scope_field] = parent

            data = dict(data)
            data["name"] = _unique_system_key(self.Meta.model, label, scope)

        return super().to_internal_value(data)


class ProvinceSerializer(SystemKeyFromLabelMixin, serializers.ModelSerializer):
    displayName = serializers.CharField(source="display_name")
    sortOrder = serializers.DecimalField(
        source="sort_order", max_digits=10, decimal_places=2, required=False
    )
    isActive = serializers.BooleanField(source="is_active", required=False)
    cityCount = serializers.SerializerMethodField()
    name = serializers.CharField(required=False)

    class Meta:
        model = Province
        fields = ["id", "name", "displayName", "sortOrder", "isActive", "cityCount"]

    def get_cityCount(self, obj) -> int:
        return obj.cities.count()

    def validate(self, attrs):
        """`name` is a system key; derive it from the label when omitted.

        The management UI only asks for the Persian label, so requiring the
        operator to also invent an English key would be pointless friction.
        """
        return _fill_name_from_display(self, attrs, Province)


class CitySerializer(SystemKeyFromLabelMixin, serializers.ModelSerializer):
    system_key_scope = "province"

    displayName = serializers.CharField(source="display_name")
    # Spell out the parent errors in Persian. DRF's defaults ("این مقدار لازم
    # است.", "pk نامعتبر ...") name no field, so a city that failed because no
    # province was chosen read as an unexplained failure in the UI.
    province = serializers.PrimaryKeyRelatedField(
        queryset=Province.objects.all(),
        error_messages={
            "required": "انتخاب استان الزامی است.",
            "null": "انتخاب استان الزامی است.",
            "does_not_exist": "استان انتخاب‌شده وجود ندارد یا حذف شده است.",
            "incorrect_type": "استان انتخاب‌شده معتبر نیست.",
        },
    )
    provinceName = serializers.CharField(
        source="province.display_name", read_only=True
    )
    sortOrder = serializers.DecimalField(
        source="sort_order", max_digits=10, decimal_places=2, required=False
    )
    isActive = serializers.BooleanField(source="is_active", required=False)
    districtCount = serializers.SerializerMethodField()
    name = serializers.CharField(required=False)

    class Meta:
        model = City
        fields = [
            "id", "name", "displayName", "province", "provinceName",
            "sortOrder", "isActive", "districtCount",
        ]

    def get_districtCount(self, obj) -> int:
        return obj.districts.count()

    def validate(self, attrs):
        attrs = _fill_name_from_display(self, attrs, City, scope_field="province")
        return attrs


class DistrictSerializer(SystemKeyFromLabelMixin, serializers.ModelSerializer):
    system_key_scope = "city"

    displayName = serializers.CharField(source="display_name")
    city = serializers.PrimaryKeyRelatedField(
        queryset=City.objects.all(),
        error_messages={
            "required": "انتخاب شهر الزامی است.",
            "null": "انتخاب شهر الزامی است.",
            "does_not_exist": "شهر انتخاب‌شده وجود ندارد یا حذف شده است.",
            "incorrect_type": "شهر انتخاب‌شده معتبر نیست.",
        },
    )
    cityName = serializers.CharField(source="city.display_name", read_only=True)
    provinceId = serializers.IntegerField(
        source="city.province_id", read_only=True
    )
    provinceName = serializers.CharField(
        source="city.province.display_name", read_only=True
    )
    fullPath = serializers.CharField(source="full_path", read_only=True)
    sortOrder = serializers.DecimalField(
        source="sort_order", max_digits=10, decimal_places=2, required=False
    )
    isActive = serializers.BooleanField(source="is_active", required=False)
    propertyCount = serializers.SerializerMethodField()
    name = serializers.CharField(required=False)

    class Meta:
        model = District
        fields = [
            "id", "name", "displayName", "city", "cityName",
            "provinceId", "provinceName", "fullPath",
            "sortOrder", "isActive", "propertyCount",
        ]

    def get_propertyCount(self, obj) -> int:
        """Existing properties here — the UI warns before deleting."""
        return obj.properties.count()

    def validate(self, attrs):
        return _fill_name_from_display(self, attrs, District, scope_field="city")


def _fill_name_from_display(serializer, attrs, model, scope_field=None):
    """Reject duplicate labels, then derive a system key when none is given.

    The operator only types the Persian label, so that is what has to be unique
    from their point of view: two «سعادت‌آباد» in one city are indistinguishable
    in a dropdown even if their generated keys differ.
    """
    from django.utils.text import slugify

    label = (attrs.get("display_name") or "").strip()

    scope = {}
    if scope_field:
        value = attrs.get(scope_field)
        if value is None and serializer.instance is not None:
            value = getattr(serializer.instance, scope_field, None)
        if value is not None:
            scope[scope_field] = value

    # --- duplicate label check -------------------------------------------
    if label:
        clash = model.objects.filter(display_name=label, **scope)
        if serializer.instance is not None:
            clash = clash.exclude(pk=serializer.instance.pk)
        if clash.exists():
            raise serializers.ValidationError(
                {"displayName": f"«{label}» در این محدوده قبلاً ثبت شده است."}
            )

    if attrs.get("name"):
        return attrs

    if serializer.instance is not None:
        # Editing: keep the existing key, it may already be referenced.
        return attrs

    attrs["name"] = _unique_system_key(model, label, scope)
    return attrs


def _unique_system_key(model, label: str, scope: dict | None = None) -> str:
    """A stable, collision-free ``name`` derived from the Persian label.

    ``slugify`` returns an empty string for a label made only of characters it
    strips (punctuation, ZWNJ, symbols), so the model name is used as the base
    in that case. The suffix loop then guarantees uniqueness — it consults
    ``all_objects`` so a soft-deleted row still reserves its key and restoring
    it can never collide with a newer one.

    The result is trimmed to the column width. A generated key must never be
    the reason a save fails: an over-long label would otherwise reach the
    database as an oversized ``varchar(100)`` and surface as a 500 instead of
    a validation message the operator can act on.
    """
    from django.utils.text import slugify

    scope = scope or {}
    max_length = model._meta.get_field("name").max_length or 100

    base = slugify((label or "").strip(), allow_unicode=True) or model.__name__.lower()
    base = base[:max_length].rstrip("-") or model.__name__.lower()

    candidate, suffix = base, 1
    while model.all_objects.filter(name=candidate, **scope).exists():
        suffix += 1
        tail = f"-{suffix}"
        candidate = f"{base[:max_length - len(tail)].rstrip('-')}{tail}"
    return candidate

