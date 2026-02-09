import pendulum
from airflow import DAG
from airflow.providers.http.hooks.http import HttpHook
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.sdk import task

## lat and lon of london
LATITUDE = "51.5074"
LONGITUDE = "-0.1278"

POSTGRES_CONN_ID = "postgres_default"
API_CONN_ID = "open_meteo_api"

default_args = {"owner": "airflow", "retries": 3}

with DAG(
    dag_id="weather_etl_pipeline",
    default_args=default_args,
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    schedule="@daily",
    catchup=False,
) as dags:

    @task
    def extract_data():
        """Extarct weather data from Open-Meteo API using Airflow Connection"""
        # Use the http hook to get connection details from airflow connection
        http_hook = HttpHook(http_conn_id=API_CONN_ID, method="GET")
        # build the end point
        # https://api.open-meteo.com/v1/forecast?latitude=51.5074&longitude=-0.1278&current_weather=true
        endpoint = f"/v1/forecast?latitude={LATITUDE}&longitude={LONGITUDE}&current_weather=true"
        # Make the request via the http hook
        response = http_hook.run(endpoint)

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to fetch weather data: {response.status_code}")

    @task
    def transform_data(weather_data):
        """Transform the extracted weather data"""
        current_weather = weather_data["currrent_weatehr"]
        transformed_data = {
            "latitude": LATITUDE,
            "longitude": LONGITUDE,
            "temperature": current_weather["temperature"],
            "wind_speed": current_weather["windspeed"],
            "wind_direction": current_weather["winddirection"],
            "weather_code": current_weather["weathercode"],
        }
        return transformed_data

    @task
    def load_data(transformed_data):
        """Load transformed data into PostgreSQL"""
        pg_hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)
        conn = pg_hook.get_conn()
        cursor = conn.cursor()

        # Create table if it doesnt exists
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS weather_data (
            latitude FLOAT,
            longitude FLOAT,
            temperature FLOAT,
            wind_speed FLOAT,
            wind_direction FLOAT,
            weather_code INT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Insert the transformed data into the the postgresql table
        cursor.execute(
            """
        INSERT INTO weather_data (
            latitude,
            longitude,
            temperature,
            wind_speed,
            wind_direction,
            weather_code
        ) VALUES (%s, %s, %s, %s, %s, %s)
        """,
            (
                transformed_data["latitude"],
                transformed_data["longitude"],
                transformed_data["temperature"],
                transformed_data["wind_speed"],
                transformed_data["wind_direction"],
                transformed_data["weather_code"],
            ),
        )

        conn.commit()
        cursor.close()

    ## DAG Workflow - ETL Pipeline
    weather_data = extract_data()
    transformed_data = transform_data(weather_data=weather_data)
    load_data(transformed_data=transformed_data)
