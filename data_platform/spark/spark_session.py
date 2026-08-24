from pyspark.sql import SparkSession

def create_spark_session() -> SparkSession:
    return (
        SparkSession.builder
        .appName("GlobalScart-DataEngineering")
        .master("local[*]")
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.sql.adaptive.enabled", "true")
        .getOrCreate()
    )

if __name__ == "__main__":
    spark = create_spark_session()
    print("Spark session created successfully")
    print(f"Spark version: {spark.version}")
    spark.stop()
