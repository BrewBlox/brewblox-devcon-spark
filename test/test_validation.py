"""
Tests brewblox_devcon_spark.validation
"""

from brewblox_devcon_spark import validation

TESTED = validation.__name__


def test_validate_api(spark_blocks):
    for obj in spark_blocks:
        validation.ApiObject.validate(obj)
