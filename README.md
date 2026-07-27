# OpenSearch

## OpenSearch Docker Compose

The instructions below are for setting up a Docker Compose cluster defined by [compose.yaml](/compose.yaml), which is based on [docker-compose-3.x.yml](https://github.com/opensearch-project/opensearch-build/blob/main/docker/release/dockercomposefiles/docker-compose-3.x.yml) which in turn uses the Docker images,  [opensearchproject/opensearch:3](https://hub.docker.com/r/opensearchproject/opensearch/tags?name=3) and [opensearchproject/opensearch-dashboards:3](https://hub.docker.com/r/opensearchproject/opensearch-dashboards/tags?name=3).
1. Set the password for `admin` account 
   ```bash
   export OPENSEARCH_INITIAL_ADMIN_PASSWORD=$(openssl rand -base64 14)
   echo "OPENSEARCH_INITIAL_ADMIN_PASSWORD=$OPENSEARCH_INITIAL_ADMIN_PASSWORD" > .env
   ```
   * Save it to the [.env](/.env) file which is ignored by [.gitignore](/.gitignore) by file
2. Start the Docker Compose cluster
   ```bash
   docker compose up -d
   ```
   * https://localhost:9200/ – [OpenSearch REST API](https://docs.opensearch.org/latest/getting-started/communicate/#opensearch-rest-api)
     ```bash
     curl -X GET "https://localhost:9200" -ku admin:$OPENSEARCH_INITIAL_ADMIN_PASSWORD
     curl -X GET "https://localhost:9200/_cat/nodes?v" -ku admin:$OPENSEARCH_INITIAL_ADMIN_PASSWORD
     curl -X GET "https://localhost:9200/_cat/plugins?v" -ku admin:$OPENSEARCH_INITIAL_ADMIN_PASSWORD
     ```
   * http://localhost:5601/ – [OpenSearch Dashboards](https://docs.opensearch.org/latest/dashboards/)
   * http://localhost:9600/ or https://localhost:9600/ – [Performance Analyzer](https://docs.opensearch.org/latest/monitoring-your-cluster/pa/index/) with `shm_file` set to `1gb` instead of the default `64mb`.
     * Performance Analyzer needs additional steps that are not documented in the steps after this note. See known issues [here](https://forum.opensearch.org/t/how-to-enable-install-performance-analyzer-on-opensearch-3-0-in-docker-compose/24468) and [here](https://github.com/opensearch-project/performance-analyzer/issues/832).
     * Create a folder under `/dev/shm` and ensure ownership is assigned properly to avoid [Error writing entry 'NOT_INITIALIZED'. Cause: /dev/shm/performanceanalyzer/xxxx.tmp](https://forum.opensearch.org/t/error-writing-entry-not-initialized-cause-dev-shm-performanceanalyzer-xxxxx-tmp/4027)
       ```bash
       mkdir /dev/shm/performanceanalyzer
       chown -R opensearch:opensearch /dev/shm/performanceanalyzer
       ```
     * Enable the Performance Analyzer plugin and check its status
       ```bash
       curl -X POST "https://localhost:9200/_plugins/_performanceanalyzer/cluster/config" -H 'Content-Type: application/json' -d '{"enabled": true}' -ku admin:$OPENSEARCH_INITIAL_ADMIN_PASSWORD
       ```
       ```bash
       curl -X GET "https://localhost:9200/_plugins/_performanceanalyzer/cluster/config" -H 'Content-Type: application/json' -ku admin:$OPENSEARCH_INITIAL_ADMIN_PASSWORD
       ```
     * Disable the Performance Analyzer plugin
       ```bash
       curl -X POST "https://localhost:9200/_plugins/_performanceanalyzer/rca/cluster/config" -H 'Content-Type: application/json' -d '{"enabled": false}' -ku admin:$OPENSEARCH_INITIAL_ADMIN_PASSWORD
       curl -X POST "https://localhost:9200/_plugins/_performanceanalyzer/cluster/config" -H 'Content-Type: application/json' -d '{"enabled": false}' -ku admin:$OPENSEARCH_INITIAL_ADMIN_PASSWORD
       ```

## Python Virtual Environment

1. Set up the virtual environment
   ```bash
   python -m venv .venv
   ```
2. Activate the virtual environment
   ```bash
   source .venv/Scripts/activate
   ```
3. Install dependencies
   ```bash
   pip install -vr requirements-dev.txt
   ```

## Stock Market Ingestion into OpenSearch

1. After setting up [Python virtual environment](#python-virtual-environment), run [src/yfinance_extract.py](/src/yfinance_extract.py) which is based on this [script](https://github.com/marsierz-ui/SPCX_data/blob/claude/dreamy-archimedes-2igl9i/collect.py) and uses the [yfinance](https://ranaroussi.github.io/yfinance/) library
   ```bash
   python src/yfinance_extract.py -t SPCX
   python src/yfinance_extract.py -t TSLA
   ```
2. [Create the index](https://docs.opensearch.org/latest/api-reference/index-apis/create-index/), `settings.index.number_of_replicas` needs to be explicitly set to `0` or the index health will be `Yellow` so it will never be accessible
   ```bash
   curl -X PUT "https://localhost:9200/ticker_history" -H 'Content-Type: application/json' -d '{"settings":{"index":{"number_of_shards":1,"number_of_replicas":0}}}' -ku admin:$OPENSEARCH_INITIAL_ADMIN_PASSWORD
   ```
   * [Delete the index](https://docs.opensearch.org/latest/api-reference/index-apis/delete-index/) if necessary
      ```bash
      curl -X DELETE "https://localhost:9200/ticker_history" -H 'Content-Type: application/json' -ku admin:$OPENSEARCH_INITIAL_ADMIN_PASSWORD
      ```
   * [Delete the documents](https://docs.opensearch.org/latest/api-reference/document-apis/delete-by-query/) in the index if needed
      ```bash
      curl -X POST "https://localhost:9200/ticker_history/_delete_by_query" -H 'Content-Type: application/json' -d '{"query":{"match_all":{}}}' -ku admin:$OPENSEARCH_INITIAL_ADMIN_PASSWORD
      ```
3. Run the PySpark job through the [spark](https://hub.docker.com/_/spark) image to read the extracts and write to OpenSearch via [src/opensearch_load.py](/src/opensearch_load.py)
   ```bash
   docker run -it --rm -v $(pwd):/opt/spark/work-dir --name spark \
      -e OPENSEARCH_INITIAL_ADMIN_PASSWORD=$OPENSEARCH_INITIAL_ADMIN_PASSWORD \
      spark:4.1.2-scala2.13-java21-python3-ubuntu \
      /opt/spark/bin/spark-submit --packages org.opensearch.client:opensearch-spark-40_2.13:2.0.0 --conf spark.jars.ivy=/opt/spark/jars /opt/spark/work-dir/src/opensearch_load.py
   ```
   * `--conf spark.jars.ivy=/opt/spark/jars` is needed to work with `--packages org.opensearch.client:opensearch-spark-40_2.13:2.0.0` (see [here](https://docs.opensearch.org/latest/clients/hadoop/)) or the following error happens
      ```
      Exception in thread "main" java.io.FileNotFoundException: /nonexistent/.ivy2.5.2/cache/resolved-org.apache.spark-spark-submit-parent-a95084db-7e12-40b2-b7f1-1e9394f2a70d-1.0.xml (No such file or directory)
      ```


## Spark Packaging Options

There was an attempt to incorporate `yfinance` into the PySpark job, but I couldn't work out the steps needed to package the libraries as per [Python Package Management](https://spark.apache.org/docs/latest/api/python/tutorial/python_packaging.html).

The instructions below are an attempt to use the [PySpark native features](https://spark.apache.org/docs/latest/api/python/tutorial/python_packaging.html#using-pyspark-native-features) that was attempted is as follows:
1. Download the [wheels](https://packaging.python.org/en/latest/specifications/binary-distribution-format/) associated with `yfinance` that would be compatible with PySpark
   ```bash
   pip download yfinance==1.5.2 \
      --platform manylinux2014_x86_64 \
      --python-version 313 \
      --only-binary=:all: \
      --dest ./wheels 
   ```
2. Add the wheels to `--py-files` argument so that it's picked up
   ```bash
   docker run -it --rm -v $(pwd):/opt/spark/work-dir --name spark \
      spark:4.1.2-scala2.13-java21-python3-ubuntu \
      /opt/spark/bin/spark-submit --py-files /opt/spark/work-dir/wheels/* /opt/spark/work-dir/src/opensearch_load.py
   ```
   * The dependency resolution didn't work as the code fails on trying to `import numpy` due to `import pandas` that `yfinance` uses internally.

Some debugging techniques that could be useful for future attempts are
* Start PySpark shell so the container remains active and use `docker exec` or `Exec` tab on Docker Desktop to check what's available to the container
   ```bash
   docker run -it --rm -v $(pwd):/opt/spark/work-dir --name spark \
      spark:4.1.2-scala2.13-java21-python3-ubuntu \
      /opt/spark/bin/pyspark
   ```
* Add `--conf spark.log.level=DEBUG` as `spark-submit` argument to propagate the [configuration parameter](https://spark.apache.org/docs/latest/configuration.html) to the PySpark application
