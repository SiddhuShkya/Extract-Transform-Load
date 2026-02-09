## ETL & Airflow Project

In this guide, we will build our first end-to-end ETL pipeline using Apache Airflow. We will utilize Astronomer to develop, deploy, and orchestrate our DAGs (Directed Acyclic Graphs), ensuring our data pipeline runs reliably on a defined schedule.

---

### 1. Initial Project Structure

> Before initializing our project structure, make sure you have astro cli installed in your machine 

```bash
siddhu@ubuntu:~$ astro version
Astro CLI Version: 1.38.1
```

> If you don't have it installed in your machine, then refer to the below links and follow their steps to install astro cli to your local machine

- [Setting Up Airflow With Astronomer (Astro)](https://github.com/SiddhuShkya/Machine-Learning-Operations/blob/main/docs/Apache-Airflow.md)

- [Astronomer Docs](https://www.astronomer.io/docs/astro/cli/overview)

After installing the astro cli, we can begin setting up our project structure. Follow the below steps

1.1 Clone the github repo and move your current directory to inside it, after that open up your VS-Code and start our project

```sh
siddhu@ubuntu:~/Desktop$ git clone git@github.com:SiddhuShkya/Weather-ETL-Pipeline.git
siddhu@ubuntu:~/Desktop$ cd Weather-ETL-Pipeline/
siddhu@ubuntu:~/Desktop/Weather-ETL-Pipeline$ code .
```

1.2 Open new terminal from inside your vs-code and initialize your new astro project

```sh
siddhu@ubuntu:~/Desktop/Weather-ETL-Pipeline$ astro dev init
/home/siddhu/Desktop/Weather-ETL-Pipeline is not an empty directory. Are you sure you want to initialize a project here? (y/n) y
Initialized empty Astro project in /home/siddhu/Desktop/Weather-ETL-Pipeline
```

1.3 Create a new dag/python script file named 'etl-weather.py' inside the dags folder. 

```text
.
├── dags
│   ├── .airflowignore
│   ├── etl-weather.py <------------------- # Your new dag file here
│   └── exampledag.py
```

1.4 Create another file 'docker-compose.yml' file as we are going to run both our airflow (astronomer) & postgres as a docker container.

> Copy paste the below yaml configurations to docker-compose.yml file

```yml
version: '3'
services: 
  postgres:
    image: postgres:13
    container_name: postgres_db
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: postgres
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

> Your final project structure should look something like the below:

```text
.
├── airflow_settings.yaml
├── .astro
│   ├── config.yaml
│   ├── dag_integrity_exceptions.txt
│   └── test_dag_integrity_default.py
├── dags
│   ├── .airflowignore
│   ├── etl-weather.py <------------------- # Your new dag file here
│   └── exampledag.py
├── Dockerfile
├── docker-compose.yml <------------------- # Your docker configuration
├── .dockerignore
├── documentation.md
├── .env
├── .git
├── .gitignore
├── include
├── LICENSE
├── packages.txt
├── plugins
├── README.md
├── requirements.txt
├── screenshots
└── tests
    └── dags
```

> This file (etl-weather.py) is the dag file we will be using to create our workflow and tasks we need to perform in our pipeline.

1.4 Add, commit and push the changes to our github

```sh
siddhu@ubuntu:~/Desktop/Weather-ETL-Pipeline$ git add .
siddhu@ubuntu:~/Desktop/Weather-ETL-Pipeline$ git commit -m 'Initial Project Structure'
siddhu@ubuntu:~/Desktop/Weather-ETL-Pipeline$ git push origin main
```

---

### 2. Weather ETL DAG

> Simply copy paste the below python script to your previously created python file (etl-weather.py)

```python
## dags/etl-weather.py

import pendulum
from airflow import DAG
from airflow.providers.https.hooks.http import HttpHook
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
```



