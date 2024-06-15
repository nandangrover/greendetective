from drf_yasg import openapi


def get_emission_factor_response():
    return openapi.Response(
        "Emission factor response",
        openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "status": openapi.Schema(
                    type=openapi.TYPE_INTEGER, description="Status code"
                ),
                "data": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    description="Emission factor data",
                    items=_emission_factor(),
                ),
            },
        ),
    )


def get_public_emission_factor_response():
    return openapi.Response(
        "Emission factor response",
        openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "status": openapi.Schema(
                    type=openapi.TYPE_INTEGER, description="Status code"
                ),
                "data": openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "item_uuid": openapi.Schema(
                            type=openapi.TYPE_STRING, description="Status code"
                        ),
                        "emission_factors": openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=_emission_factor(public=True),
                        ),
                    },
                    description="Emission factor data",
                ),
            },
        ),
    )


def _emission_factor(public=False):
    return openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "main_item_uuid": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="UUID which is a combination of item_uuid + breakdown_uuid + em_factor_uuid, if there is no related item else item_uuid",
            ),
            "main_provider_uuid": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="UUID of the main provider (only valid if calculation_level is 'P')",
            ),
            "category": openapi.Schema(
                type=openapi.TYPE_STRING, description="Category name"
            ),
            "name": openapi.Schema(
                type=openapi.TYPE_STRING, description="Name of the item"
            ),
            "taxonomy": openapi.Schema(
                type=openapi.TYPE_STRING, description="Taxonomy"
            ),
            "em_factor": openapi.Schema(
                type=openapi.TYPE_NUMBER, description="Emission factor"
            ),
            "average_weight": openapi.Schema(
                type=openapi.TYPE_NUMBER, description="Average weight"
            ),
            "method": openapi.Schema(type=openapi.TYPE_STRING, description="Method"),
            "em_factor_datetime": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Emission factor datetime",
            ),
            "reporting_approach": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Reporting approach",
            ),
            "calculation_level": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Calculation level",
            ),
            "source": openapi.Schema(
                type=openapi.TYPE_OBJECT,
                description="Source",
                properties={
                    "link": openapi.Schema(
                        type=openapi.TYPE_STRING, description="Link"
                    ),
                    "name": openapi.Schema(
                        type=openapi.TYPE_STRING, description="Name"
                    ),
                    "year": openapi.Schema(
                        type=openapi.TYPE_STRING, description="Year"
                    ),
                },
            ),
            "matching_meta": openapi.Schema(
                type=openapi.TYPE_OBJECT,
                description="Semantic or manual match meta",
                properties={
                    "related_item_uuid": openapi.Schema(
                        type=openapi.TYPE_STRING,
                        description="UUID which is a combination of item_uuid + breakdown_uuid + em_factor_uuid, if there is no related item then it's empty",
                    ),
                    "item_relation_score": openapi.Schema(
                        type=openapi.TYPE_NUMBER,
                        description="Semantic match score. Will be 0 if the returned emission factor is not from a related item. Will be 1 if the returned emission factor is a manual match. Will be between 0 and 1 if the returned emission factor is from a semantic match. Will be null if semantic match is using traversed relation (Item A -> Item B -> Item C)",
                    ),
                    "related_provider_uuid": openapi.Schema(
                        type=openapi.TYPE_STRING,
                        description="UUID of the related provider",
                    ),
                    "provider_relation_score": openapi.Schema(
                        type=openapi.TYPE_NUMBER,
                        description="Semantic match score between the provider of the main provider and the related provider. Will be 0 if the returned emission factor is not from a related provider. Will be 1 if the returned emission factor is a manual match. Will be between 0 and 1 if the returned emission factor is from a semantic match. Will be null if semantic match is using traversed relation (Provider A -> Provider B -> Provider C)",
                    ),
                },
            ),
            "ghgp_category": openapi.Schema(
                type=openapi.TYPE_STRING, description="GHGP category"
            ) if public else None,
            "ignored_parameters": openapi.Schema(
                type=openapi.TYPE_OBJECT,
                description="Ignored parameters",
                properties={
                    "provider_name": openapi.Schema(
                        type=openapi.TYPE_STRING, description="Provider name"
                    ),
                    "provider_country_code": openapi.Schema(
                        type=openapi.TYPE_STRING, description="Provider country code"
                    ),
                    "country_code": openapi.Schema(
                        type=openapi.TYPE_STRING, description="Country code"
                    ),
                    "spend_category_name": openapi.Schema(
                        type=openapi.TYPE_STRING, description="Spend category name"
                    ),
                },
            ),
        },
    )


def get_item_response():
    return openapi.Response(
        "Item response",
        openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "status": openapi.Schema(
                    type=openapi.TYPE_INTEGER, description="Status code"
                ),
                "data": openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    description="Item data",
                    properties={
                        "uuid": openapi.Schema(
                            type=openapi.TYPE_STRING, description="UUID of the item"
                        ),
                        "name": openapi.Schema(
                            type=openapi.TYPE_STRING, description="Name of the item"
                        ),
                        "sub_name": openapi.Schema(
                            type=openapi.TYPE_STRING, description="Sub name of the item"
                        ),
                        "description": openapi.Schema(
                            type=openapi.TYPE_STRING,
                            description="Description of the item",
                        ),
                        "related_items": openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            description="List of related item UUIDs",
                            items=openapi.Items(type=openapi.TYPE_STRING),
                        ),
                        "callback": openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            description="Callback data",
                            items=openapi.Items(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    "uuid": openapi.Schema(type=openapi.TYPE_STRING),
                                    "url": openapi.Schema(type=openapi.TYPE_STRING),
                                    "method": openapi.Schema(type=openapi.TYPE_STRING),
                                },
                            ),
                        ),
                        "item_breakdown": openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            description="Item breakdown data",
                            items=openapi.Items(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    "uuid": openapi.Schema(type=openapi.TYPE_STRING),
                                    "ghgp_category": openapi.Schema(
                                        type=openapi.TYPE_STRING
                                    ),
                                    "calculation_level": openapi.Schema(
                                        type=openapi.TYPE_STRING
                                    ),
                                    "extra_attributes": openapi.Schema(
                                        type=openapi.TYPE_OBJECT
                                    ),
                                    "reporting_approach": openapi.Schema(
                                        type=openapi.TYPE_STRING
                                    ),
                                    "provider": openapi.Schema(
                                        type=openapi.TYPE_ARRAY,
                                        items=openapi.Items(type=openapi.TYPE_OBJECT),
                                    ),
                                    "spend_category": openapi.Schema(
                                        type=openapi.TYPE_ARRAY,
                                        items=openapi.Items(type=openapi.TYPE_OBJECT),
                                    ),
                                    "emission_breakdown": openapi.Schema(
                                        type=openapi.TYPE_ARRAY,
                                        items=openapi.Items(
                                            type=openapi.TYPE_OBJECT,
                                            properties={
                                                "uuid": openapi.Schema(
                                                    type=openapi.TYPE_STRING
                                                ),
                                                "category_name": openapi.Schema(
                                                    type=openapi.TYPE_STRING
                                                ),
                                                "average_weight": openapi.Schema(
                                                    type=openapi.TYPE_NUMBER
                                                ),
                                                "em_date": openapi.Schema(
                                                    type=openapi.TYPE_STRING
                                                ),
                                                "emission_factor": openapi.Schema(
                                                    type=openapi.TYPE_ARRAY,
                                                    items=openapi.Items(
                                                        type=openapi.TYPE_OBJECT,
                                                        properties={
                                                            "uuid": openapi.Schema(
                                                                type=openapi.TYPE_STRING
                                                            ),
                                                            "breakdown_name": openapi.Schema(
                                                                type=openapi.TYPE_STRING
                                                            ),
                                                            "em_factor": openapi.Schema(
                                                                type=openapi.TYPE_NUMBER
                                                            ),
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
                                                "symbol": openapi.Schema(
                                                    type=openapi.TYPE_STRING
                                                ),
                                            },
                                        ),
                                    ),
                                    "currency": openapi.Schema(
                                        type=openapi.TYPE_ARRAY,
                                        items=openapi.Items(type=openapi.TYPE_OBJECT),
                                    ),
                                    "origin": openapi.Schema(
                                        type=openapi.TYPE_ARRAY,
                                        items=openapi.Items(
                                            type=openapi.TYPE_OBJECT,
                                            properties={
                                                "uuid": openapi.Schema(
                                                    type=openapi.TYPE_STRING
                                                ),
                                                "address_line_1": openapi.Schema(
                                                    type=openapi.TYPE_STRING,
                                                    x_nullable=True,
                                                ),
                                                "address_line_2": openapi.Schema(
                                                    type=openapi.TYPE_STRING,
                                                    x_nullable=True,
                                                ),
                                                "town_or_city": openapi.Schema(
                                                    type=openapi.TYPE_STRING,
                                                    x_nullable=True,
                                                ),
                                                "postcode": openapi.Schema(
                                                    type=openapi.TYPE_STRING,
                                                    x_nullable=True,
                                                ),
                                                "country_region": openapi.Schema(
                                                    type=openapi.TYPE_STRING,
                                                    x_nullable=True,
                                                ),
                                                "country": openapi.Schema(
                                                    type=openapi.TYPE_STRING
                                                ),
                                                "country_code": openapi.Schema(
                                                    type=openapi.TYPE_STRING
                                                ),
                                                "latitude": openapi.Schema(
                                                    type=openapi.TYPE_NUMBER,
                                                    x_nullable=True,
                                                ),
                                                "longitude": openapi.Schema(
                                                    type=openapi.TYPE_NUMBER,
                                                    x_nullable=True,
                                                ),
                                            },
                                        ),
                                    ),
                                },
                            ),
                        ),
                    },
                ),
            },
        ),
    )

def delete_item_response():
    return openapi.Response(
        "Delete item response",
        openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "status": openapi.Schema(
                    type=openapi.TYPE_INTEGER, description="Status code"
                ),
                "data": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Delete item data",
                ),
            },
        ),
    )
def delete_provider_response():
    return openapi.Response(
        "Delete provider response",
        openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "status": openapi.Schema(
                    type=openapi.TYPE_INTEGER, description="Status code"
                ),
                "data": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Delete provider data",
                ),
            },
        ),
    )
