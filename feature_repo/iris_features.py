import os
from datetime import timedelta

from feast import BigQuerySource, Entity, FeatureView, Field, ValueType
from feast.types import Float32


PROJECT_ID = os.getenv("PROJECT_ID", "your-gcp-project-id")
BIGQUERY_DATASET = os.getenv("BIGQUERY_DATASET", "iris_feast_week4")
BIGQUERY_TABLE = os.getenv("BIGQUERY_TABLE", "iris_features")

iris_sample = Entity(
    name="iris_sample",
    join_keys=["sample_id"],
    value_type=ValueType.INT64,
    description="One Iris flower sample identified by a stable sample id.",
)

iris_source = BigQuerySource(
    name="iris_source",
    table_ref=f"{PROJECT_ID}.{BIGQUERY_DATASET}.{BIGQUERY_TABLE}",
    timestamp_field="event_timestamp",
)

iris_feature_view = FeatureView(
    name="iris_features",
    entities=[iris_sample],
    ttl=timedelta(days=3650),
    schema=[
        Field(name="sepal_length", dtype=Float32),
        Field(name="sepal_width", dtype=Float32),
        Field(name="petal_length", dtype=Float32),
        Field(name="petal_width", dtype=Float32),
    ],
    source=iris_source,
)
