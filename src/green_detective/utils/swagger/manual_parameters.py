from drf_yasg import openapi


def get_emission_factor_parameters():
    return [
        openapi.Parameter(
            "uuid",
            openapi.IN_QUERY,
            description="UUID of the item",
            type=openapi.TYPE_STRING,
        ),
        openapi.Parameter(
            "spend_category",
            openapi.IN_QUERY,
            description="Spend category name. Either name or spend_category is required",
            type=openapi.TYPE_STRING,
        ),
        openapi.Parameter(
            "name",
            openapi.IN_QUERY,
            description="Name of the item. Either name or spend_category is required",
            type=openapi.TYPE_STRING,
        ),
        openapi.Parameter(
            "sub_name",
            openapi.IN_QUERY,
            description="Sub name of the item",
            type=openapi.TYPE_STRING,
        ),
        openapi.Parameter(
            "description",
            openapi.IN_QUERY,
            description="Description of the item",
            type=openapi.TYPE_STRING,
        ),
        openapi.Parameter(
            "country_code",
            openapi.IN_QUERY,
            description="Country code. If not found, fallback will be used",
            type=openapi.TYPE_STRING,
        ),
        openapi.Parameter(
            "unit_name",
            openapi.IN_QUERY,
            description="Unit name. Either unit or currency_code is required",
            type=openapi.TYPE_STRING,
        ),
        openapi.Parameter(
            "unit_symbol",
            openapi.IN_QUERY,
            description="Unit symbol. Either unit or currency_code is required",
            type=openapi.TYPE_STRING,
        ),
        openapi.Parameter(
            "currency_code",
            openapi.IN_QUERY,
            description="Currency code. Required if spend_category is provided. Either unit or currency_code is required",
            type=openapi.TYPE_STRING,
        ),
        openapi.Parameter(
            "provider_name",
            openapi.IN_QUERY,
            description="Provider name. If not found, fallback will be used",
            type=openapi.TYPE_STRING,
        ),
        openapi.Parameter(
            "provider_country_code",
            openapi.IN_QUERY,
            description="Provider country code. If not found, fallback will be used",
            type=openapi.TYPE_STRING,
        ),
        openapi.Parameter(
            "calculation_level",
            openapi.IN_QUERY,
            description="Calculation level. Can be either 'I', 'SC' or 'P'. Will be used to filter provider breakdowns. Empty returns all",
            type=openapi.TYPE_STRING,
        ),
        openapi.Parameter(
            "ghgp_category",
            openapi.IN_QUERY,
            description="GHGP category",
            type=openapi.TYPE_STRING,
        ),
        openapi.Parameter(
            "extra_attributes",
            openapi.IN_QUERY,
            description="Extra attributes. Saved as JSON. Example: {'abv': '5.2'}",
            type=openapi.TYPE_STRING,
        ),
        openapi.Parameter(
            "reporting_approach",
            openapi.IN_QUERY,
            description="Reporting approach",
            type=openapi.TYPE_STRING,
        ),
        openapi.Parameter(
            "method",
            openapi.IN_QUERY,
            description="Can be either 'method', 'scope' or 'quantity'. Will be used to filter provider breakdowns. Empty returns all",
            type=openapi.TYPE_STRING,
        ),
        openapi.Parameter(
            "breakdown_category",
            openapi.IN_QUERY,
            description="Breakdown category. Example: General, Fuel and Energy, etc. Empty returns all",
            type=openapi.TYPE_STRING,
        ),
        openapi.Parameter(
            "source_name",
            openapi.IN_QUERY,
            description="Source name. If not found, fallback will be used",
            type=openapi.TYPE_STRING,
        ),
        openapi.Parameter(
            "source_year",
            openapi.IN_QUERY,
            description="Source year. If not found, fallback will be used",
            type=openapi.TYPE_STRING,
        ),
        openapi.Parameter(
            "em_date",
            openapi.IN_QUERY,
            description="Emission date. Format: YYYY-MM-DD HH:MM. Empty returns all",
            type=openapi.TYPE_STRING,
        ),
        openapi.Parameter(
            "language",
            openapi.IN_QUERY,
            description="Language code",
            type=openapi.TYPE_STRING,
        ),
    ]


def get_public_emission_factor_parameters():
    return [
        openapi.Parameter(
            "uuid",
            openapi.IN_QUERY,
            description="UUID of the item",
            type=openapi.TYPE_STRING,
        ),
        openapi.Parameter(
            "spend_category",
            openapi.IN_QUERY,
            description="Spend category name. Either name or spend_category is required",
            type=openapi.TYPE_STRING,
        ),
        openapi.Parameter(
            "name",
            openapi.IN_QUERY,
            description="Name of the item. Either name or spend_category is required",
            type=openapi.TYPE_STRING,
            required=True,
        ),
        openapi.Parameter(
            "sub_name",
            openapi.IN_QUERY,
            description="Sub name of the item",
            type=openapi.TYPE_STRING,
        ),
        openapi.Parameter(
            "description",
            openapi.IN_QUERY,
            description="Description of the item",
            type=openapi.TYPE_STRING,
        ),
        openapi.Parameter(
            "country_code",
            openapi.IN_QUERY,
            description="Country code. If not found, fallback will be used",
            type=openapi.TYPE_STRING,
        ),
        openapi.Parameter(
            "unit_name",
            openapi.IN_QUERY,
            description="Unit name. Either unit or currency_code is required",
            type=openapi.TYPE_STRING,
            required=True,
        ),
        openapi.Parameter(
            "unit_symbol",
            openapi.IN_QUERY,
            description="Unit symbol. Either unit or currency_code is required",
            type=openapi.TYPE_STRING,
        ),
        openapi.Parameter(
            "currency_code",
            openapi.IN_QUERY,
            description="Currency code. Required if spend_category is provided. Either unit or currency_code is required",
            type=openapi.TYPE_STRING,
        ),
        openapi.Parameter(
            "provider_name",
            openapi.IN_QUERY,
            description="Provider name. If not found, fallback will be used",
            type=openapi.TYPE_STRING,
        ),
        openapi.Parameter(
            "provider_country_code",
            openapi.IN_QUERY,
            description="Provider country code. If not found, fallback will be used",
            type=openapi.TYPE_STRING,
        ),
        openapi.Parameter(
            "calculation_level",
            openapi.IN_QUERY,
            description="Calculation level. Can be either 'I', 'SC' or 'P'. Will be used to filter provider breakdowns. Empty returns all",
            type=openapi.TYPE_STRING,
        ),
        openapi.Parameter(
            "ghgp_category",
            openapi.IN_QUERY,
            description="GHGP category",
            type=openapi.TYPE_STRING,
            required=True,
        ),
        openapi.Parameter(
            "extra_attributes",
            openapi.IN_QUERY,
            description="Extra attributes. Saved as JSON. Example: {'abv': '5.2'}",
            type=openapi.TYPE_STRING,
        ),
        openapi.Parameter(
            "reporting_approach",
            openapi.IN_QUERY,
            description="Reporting approach",
            type=openapi.TYPE_STRING,
        ),
        openapi.Parameter(
            "method",
            openapi.IN_QUERY,
            description="Can be either 'method', 'scope' or 'quantity'. Will be used to filter provider breakdowns. Empty returns all",
            type=openapi.TYPE_STRING,
        ),
        openapi.Parameter(
            "breakdown_category",
            openapi.IN_QUERY,
            description="Breakdown category. Example: General, Fuel and Energy, etc. Empty returns all",
            type=openapi.TYPE_STRING,
        ),
        openapi.Parameter(
            "source_name",
            openapi.IN_QUERY,
            description="Source name. If not found, fallback will be used",
            type=openapi.TYPE_STRING,
        ),
        openapi.Parameter(
            "source_year",
            openapi.IN_QUERY,
            description="Source year. If not found, fallback will be used",
            type=openapi.TYPE_STRING,
        ),
        openapi.Parameter(
            "em_date",
            openapi.IN_QUERY,
            description="Emission date. Format: YYYY-MM-DD HH:MM. Empty returns all",
            type=openapi.TYPE_STRING,
        ),
    ]


def get_item_parameters():
    return [
        openapi.Parameter(
            "uuid",
            openapi.IN_QUERY,
            description="UUID of the item",
            type=openapi.TYPE_STRING,
        ),
        openapi.Parameter(
            "name",
            openapi.IN_QUERY,
            description="Name of the item",
            type=openapi.TYPE_STRING,
        ),
        openapi.Parameter(
            "sub_name",
            openapi.IN_QUERY,
            description="Sub name of the item",
            type=openapi.TYPE_STRING,
        ),
        openapi.Parameter(
            "description",
            openapi.IN_QUERY,
            description="Description of the item",
            type=openapi.TYPE_STRING,
        ),
        openapi.Parameter(
            "related_items",
            openapi.IN_QUERY,
            description="List of related item UUIDs",
            type=openapi.TYPE_ARRAY,
            items=openapi.Items(type=openapi.TYPE_STRING),
        ),
        openapi.Parameter(
            "callback",
            openapi.IN_QUERY,
            description="Callback data",
            type=openapi.TYPE_ARRAY,
            items=openapi.Items(
                type=openapi.TYPE_OBJECT,
                properties={
                    "uuid": openapi.Schema(type=openapi.TYPE_STRING),
                    "url": openapi.Schema(type=openapi.TYPE_STRING),
                    "method": openapi.Schema(type=openapi.TYPE_STRING),
                },
            ),
        ),
        openapi.Parameter(
            "item_breakdown",
            openapi.IN_QUERY,
            description="Item breakdown data",
            type=openapi.TYPE_ARRAY,
            items=openapi.Items(
                type=openapi.TYPE_OBJECT,
                properties={
                    "uuid": openapi.Schema(type=openapi.TYPE_STRING),
                    "ghgp_category": openapi.Schema(type=openapi.TYPE_STRING),
                    "calculation_level": openapi.Schema(type=openapi.TYPE_STRING),
                    "extra_attributes": openapi.Schema(type=openapi.TYPE_OBJECT),
                    "reporting_approach": openapi.Schema(type=openapi.TYPE_STRING),
                    "provider": openapi.Schema(
                        type=openapi.TYPE_ARRAY, items=openapi.Items(type=openapi.TYPE_OBJECT)
                    ),
                    "spend_category": openapi.Schema(
                        type=openapi.TYPE_ARRAY, items=openapi.Items(type=openapi.TYPE_OBJECT)
                    ),
                    "emission_breakdown": openapi.Schema(
                        type=openapi.TYPE_ARRAY,
                        items=openapi.Items(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                "uuid": openapi.Schema(type=openapi.TYPE_STRING),
                                "category_name": openapi.Schema(type=openapi.TYPE_STRING),
                                "average_weight": openapi.Schema(type=openapi.TYPE_NUMBER),
                                "em_date": openapi.Schema(type=openapi.TYPE_STRING),
                                "emission_factor": openapi.Schema(
                                    type=openapi.TYPE_ARRAY,
                                    items=openapi.Items(
                                        type=openapi.TYPE_OBJECT,
                                        properties={
                                            "uuid": openapi.Schema(type=openapi.TYPE_STRING),
                                            "breakdown_name": openapi.Schema(
                                                type=openapi.TYPE_STRING
                                            ),
                                            "em_factor": openapi.Schema(type=openapi.TYPE_NUMBER),
                                            "source": openapi.Schema(
                                                type=openapi.TYPE_ARRAY,
                                                items=openapi.Items(
                                                    type=openapi.TYPE_OBJECT,
                                                    properties={
                                                        "uuid": openapi.Schema(
                                                            type=openapi.TYPE_STRING
                                                        ),
                                                        "name": openapi.Schema(
                                                            type=openapi.TYPE_STRING
                                                        ),
                                                        "link": openapi.Schema(
                                                            type=openapi.TYPE_STRING
                                                        ),
                                                        "year": openapi.Schema(
                                                            type=openapi.TYPE_STRING
                                                        ),
                                                    },
                                                ),
                                            ),
                                        },
                                    ),
                                ),
                            },
                        ),
                    ),
                    "unit": openapi.Schema(
                        type=openapi.TYPE_ARRAY, items=openapi.Items(type=openapi.TYPE_OBJECT)
                    ),
                    "currency": openapi.Schema(
                        type=openapi.TYPE_ARRAY, items=openapi.Items(type=openapi.TYPE_OBJECT)
                    ),
                    "origin": openapi.Schema(
                        type=openapi.TYPE_ARRAY, items=openapi.Items(type=openapi.TYPE_OBJECT)
                    ),
                },
            ),
        ),
    ]
