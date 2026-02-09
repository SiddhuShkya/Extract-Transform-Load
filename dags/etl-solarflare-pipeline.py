from airflow import DAG
from airflow.providers.http.operators.http import HttpOperator
from airflow.sdk import task
from airflow.providers.postgres.hooks.postgres import PostgresHook
import pendulum
from datetime import timedelta

## Define the DAG
with DAG(
    dag_id="solarflare_etl_pipeline",
    start_date=pendulum.datetime(2025, 1, 1, tz="UTC"),
    schedule="@daily",
    catchup=False,
) as dag:
    ## Step 1: Create the Postgres table if it doesn't exist
    @task
    def create_postgres_table():
        postgres_hook = PostgresHook(postgres_conn_id="my_postgres_connection")
        # Create a fresh table
        create_table_query = """
        CREATE TABLE IF NOT EXISTS solar_flare_data (
            id SERIAL PRIMARY KEY,
            flr_id VARCHAR(50) UNIQUE,
            class_type VARCHAR(10),
            begin_time TIMESTAMP,
            peak_time TIMESTAMP,
            end_time TIMESTAMP,
            source_location VARCHAR(20),
            active_region_num INT,
            link TEXT
        );
        """
        postgres_hook.run(create_table_query)

    ## Step 2: Extract DONKI Solar Flare data
    extract_solarflare_data = HttpOperator(
        task_id="extract_solarflare",
        http_conn_id="nasa_api",
        endpoint="DONKI/FLR?api_key={{ conn.nasa_api.extra_dejson.api_key }}",
        method="GET",
        response_filter=lambda response: response.json(),
        log_response=True,
        retries=3,
        retry_delay=timedelta(minutes=5),
    )

    ## Step 3: Transform the data (keep only important fields)
    @task
    def transform_flr_data(response):
        transformed = []
        for flare in response:
            transformed.append(
                {
                    "flr_id": flare.get("flrID"),
                    "class_type": flare.get("classType"),
                    "begin_time": flare.get("beginTime"),
                    "peak_time": flare.get("peakTime"),
                    "end_time": flare.get("endTime"),
                    "source_location": flare.get("sourceLocation"),
                    "active_region_num": flare.get("activeRegionNum"),
                    "link": flare.get("link"),
                }
            )
        return transformed

    ## Step 4: Load data into Postgres
    @task
    def load_data_postgres(flare_data):
        postgres_hook = PostgresHook(postgres_conn_id="my_postgres_connection")
        insert_query = """
        INSERT INTO solar_flare_data 
        (flr_id, class_type, begin_time, peak_time, end_time, source_location, active_region_num, link)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (flr_id) DO NOTHING;  -- prevent duplicates
        """
        for flare in flare_data:
            postgres_hook.run(
                insert_query,
                parameters=(
                    flare["flr_id"],
                    flare["class_type"],
                    flare["begin_time"],
                    flare["peak_time"],
                    flare["end_time"],
                    flare["source_location"],
                    flare["active_region_num"],
                    flare["link"],
                ),
            )

    ## Step 5: Define task dependencies
    # Extract
    create_postgres_table() >> extract_solarflare_data
    api_response = extract_solarflare_data.output
    # Transform
    transformed_data = transform_flr_data(api_response)
    # Load
    load_data_postgres(transformed_data)
