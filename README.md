# OpenSearch

* [Local Setup](#local-setup) – Prerequisites for local development
* [Ingestion into OpenSearch](#ingestion-into-opensearch) – Data ingestion into OpenSearch
* [OpenSearch Dashboards](#opensearch-dashboards) – Visualizations and data dashboards via OpenSearch Dashboards 

## Local Setup

* [OpenSearch Docker Compose Cluster](#opensearch-docker-compose-cluster) – Local OpenSearch node and dashboards
* [Python Virtual Environment](#python-virtual-environment) – Enable IDE to check method signatures and run certain scripts locally

### OpenSearch Docker Compose Cluster

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

### Python Virtual Environment

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

## Ingestion into OpenSearch

There are two variants for loading OpenSearch that do the same thing to leverage ticker data from Yahoo! Finance
* [PySpark](#pyspark)
  * [Apache Spark Python Packaging Options](#apache-spark-python-packaging-options)
* [AWS Glue](#aws-glue)
  * [AWS Glue Python Packaging Options](#aws-glue-python-packaging-options)

The instructions below are to create/maintain the `ticker_history` index that will be used to hold the data to be loaded
* [Create the index](https://docs.opensearch.org/latest/api-reference/index-apis/create-index/), `settings.index.number_of_replicas` needs to be explicitly set to `0` or the index health will be `Yellow` so it will never be accessible
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

### PySpark

The instructions below use a utility script to save the necessary ticker data into the [temp/](/temp) folder and Apache Spark 4.1.2, specifically PySpark to upsert the data into OpenSearch index, `ticker_history`.
1. After setting up [Python virtual environment](#python-virtual-environment), run [src/yfinance_extract.py](/src/yfinance_extract.py) which is based on this [script](https://github.com/marsierz-ui/SPCX_data/blob/claude/dreamy-archimedes-2igl9i/collect.py) and uses the [yfinance](https://ranaroussi.github.io/yfinance/) library to download ticker data
   ```bash
    ticker_symbols=( 'AAPL' 'NVDA' 'GOOG' 'MSFT' 'AMZN' 'AVGO' 'META' 'SPCX' 'TSLA' 'WMT' 'SKHY' 'MU' 'AMD' 'ASML' 'CSCO' 'COST' 'INTC' 'AMAT' 'LRCX' 'NFLX' 'PLTR' 'PANW' 'TXN' 'ARM' 'LIN' 'KLAC' 'AMGN' 'PEP' 'TMUS' 'CRWD' 'ADI' 'STX' 'SHOP' 'GILD' 'QCOM' 'WDC' 'BKNG' 'SNDK' 'IBKR' 'MRVL' 'APP' 'PDD' 'ISRG' 'VRTX' 'SBUX' 'FTNT' 'ADP' 'SNY' 'ADBE' 'MAR' 'EQIX' 'CME' 'MNST' 'MELI' 'DDOG' 'CSX' 'CEG' 'CDNS' 'INTU' 'ABNB' 'CMCSA' 'CTAS' 'DASH' 'MDLZ' 'NTES' 'HOOD' 'ROST' 'HON' 'ORLY' 'REGN' 'SNPS' 'PCAR' 'AEP' )
    
    for symbol in "${ticker_symbols[@]}"; do
        echo "Extracting data for $symbol..."
        python src/yfinance_extract.py -t "$symbol"
    done
   ```
2. Run the PySpark job through the [spark](https://hub.docker.com/_/spark) image to read the extracts and write to OpenSearch via [src/opensearch_load.py](/src/opensearch_load.py)
   ```bash
   docker run -it --rm --name spark \
      -v $(pwd):/opt/spark/work-dir \
      -e OPENSEARCH_INITIAL_ADMIN_PASSWORD=$OPENSEARCH_INITIAL_ADMIN_PASSWORD \
      spark:4.1.2-scala2.13-java21-python3-ubuntu \
      /opt/spark/bin/spark-submit --packages org.opensearch.client:opensearch-spark-40_2.13:2.0.0 --conf spark.jars.ivy=/opt/spark/jars /opt/spark/work-dir/src/opensearch_load.py
   ```
   * `--conf spark.jars.ivy=/opt/spark/jars` is needed to work with `--packages org.opensearch.client:opensearch-spark-40_2.13:2.0.0` (see [here](https://docs.opensearch.org/latest/clients/hadoop/)) or the following error happens
      ```
      Exception in thread "main" java.io.FileNotFoundException: /nonexistent/.ivy2.5.2/cache/resolved-org.apache.spark-spark-submit-parent-a95084db-7e12-40b2-b7f1-1e9394f2a70d-1.0.xml (No such file or directory)
      ```

#### Apache Spark Python Packaging Options

It is possible to combine the two steps and incorporate `yfinance` into the PySpark job, but further research and development is needed on the [Python Package Management](https://spark.apache.org/docs/latest/api/python/tutorial/python_packaging.html) documentation to pull it off. The options that are mentioned in the documentation are summarized below as follows:
* [Using PySpark Native Features](https://spark.apache.org/docs/latest/api/python/tutorial/python_packaging.html#using-pyspark-native-features) – This approach was attempted with instructions further below
* [Using Conda](https://spark.apache.org/docs/latest/api/python/tutorial/python_packaging.html#using-conda) – Use a [Conda](https://docs.conda.io/en/latest/) environment to ship the packages via [conda-pack](https://conda.github.io/conda-pack/spark.html) to create relocatable Conda environments which are loaded through either `--archives` option or `spark.archives` configuration
* [Using Virtualenv](https://spark.apache.org/docs/latest/api/python/tutorial/python_packaging.html#using-virtualenv) – Use a [virtualenv](https://virtualenv.pypa.io/en/latest/) environment (i.e., [venv](https://docs.python.org/3/library/venv.html) module) to ship the packages via [venv-pack](https://jcristharif.com/venv-pack/index.html) to create Virtualenv environments which are loaded through either `--archives` option or `spark.archives` configuration
* [Using PEX](https://spark.apache.org/docs/latest/api/python/tutorial/python_packaging.html#using-pex) – Use [PEX](https://github.com/pantsbuild/pex) to ship `.pex` executable file with a self-contained Python environment similar to Conda or virtualenv which is loaded through either `--files` option or `spark.files` configuration
* [Using uv run](https://spark.apache.org/docs/latest/api/python/tutorial/python_packaging.html#using-uv-run) – Create a wrapper script that executes `uv run` that is referenced by `PYSPARK_PYTHON` environment variable and [PEP 723 inline script metadata](https://docs.astral.sh/uv/guides/scripts/#declaring-script-dependencies) to declare the dependencies
  * **Note:** This approach appears to be the most promising as it doesn't require packaging offline and could possibly run on startup of the Docker container

An attempt to use the [PySpark native features](https://spark.apache.org/docs/latest/api/python/tutorial/python_packaging.html#using-pyspark-native-features) was made as follows, but ultimately failed due to `pip install` and Python wheels not being supported to pass the necessary libraries to the Spark worker:
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
   * The dependency resolution failure seems to be due to wheels not being supported as per the documentation
     > PySpark allows to upload Python files (`.py`), zipped Python packages (`.zip`), and Egg files (`.egg`) to the executors by one of the following:
     > 
     > ...
     > 
     > However, it does not allow to add packages built as [Wheels](https://www.python.org/dev/peps/pep-0427/) and therefore does not allow to include dependencies with native code.
   * **Note:** `pip install` requires `--target` because `HOME=/nonexistent` so the command will fail on the default pip cache location, `~/.cache/pip`
     ```bash
     python3 -m pip install yfinance==1.5.2 --target /opt/spark/python/lib/
     ```
     * `--only-binary=:all:` was considered an option to ensure the wheel is saved to the target location, but it doesn't seem to be applied

Some debugging techniques that could be useful for future attempts are
* Start PySpark shell so the container remains active and use `docker exec` or `Exec` tab on Docker Desktop to check what's available to the container
   ```bash
   docker run -it --rm -v $(pwd):/opt/spark/work-dir --name spark \
      spark:4.1.2-scala2.13-java21-python3-ubuntu \
      /opt/spark/bin/pyspark
   ```
* Add `--conf spark.log.level=DEBUG` as `spark-submit` argument to propagate the [configuration parameter](https://spark.apache.org/docs/latest/configuration.html) to the PySpark application

### AWS Glue

The instructions below combine the two separate steps from [PySpark](#pyspark) with the [amazon/aws-glue-libs](https://hub.docker.com/r/amazon/aws-glue-libs) image which can install Python modules. AWS Glue 5.0 [supports](https://docs.aws.amazon.com/glue/latest/dg/release-notes.html) Apache Spark 3.5.4, Python 3.11, Scala 2.12.8, and Java 17.
1. Run the AWS Glue job through the `amazon/aws-glue-libs` image to read ticker data from Yahoo! Finance and write to OpenSearch via [src/yfinance_to_opensearch.py](/src/yfinance_to_opensearch.py). The Docker image doesn't support the `--additional-python-modules` argument available to the actual AWS Glue service, so `python3 -m pip install` is used instead.
   ```bash
   docker run -it --rm --name glue5_spark_submit \
       -v $(pwd):/opt/hadoop/workspace \
       -e OPENSEARCH_INITIAL_ADMIN_PASSWORD=$OPENSEARCH_INITIAL_ADMIN_PASSWORD \
       amazon/aws-glue-libs:5.0.9 \
       -c "python3 -m pip install \"yfinance==1.5.2\" && spark-submit --packages org.opensearch.client:opensearch-spark-35_2.12:2.0.0 /opt/hadoop/workspace/src/yfinance_to_opensearch.py"
   ```

#### AWS Glue Python Packaging Options

The AWS Glue equivalent of what we're trying to do with [Apache Spark](#apache-spark-python-packaging-options) is documented in [Using Python libraries with AWS Glue](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-python-libraries.html) with the following options
* "Installing additional Python libraries in AWS Glue 5.0 or above using Zip of Wheels"
  > --additional-python-modules s3://amzn-s3-demo-bucket/path/to/zip-of-wheels-1.0.0.gluewheels.zip --python-modules-installer-option --no-index
  * See [Appendix A: Creating a Zip of Wheels Artifact](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-python-libraries.html#glue-python-library-zip-of-wheels-appendix) for how to assemble a zip of wheel artifact
* "Installing additional Python libraries using Wheel"
  > --additional-python-modules s3://amzn-s3-demo-bucket/path/to/package-1.0.0-py3-none-any.whl,s3://your-bucket/path/to/another-package-2.1.0-cp311-cp311-linux_x86_64.whl
* "Installing additional Python libraries in AWS Glue 5.0 or above using requirements.txt"
  > --additional-python-modules s3://path_to_requirements.txt  --python-modules-installer-option -r
* "Installing additional Python libraries directly configuring as comma separated list"
  > --additional-python-modules scikit-learn==0.21.3,ephem==4.1.6
* "Including Python files with PySpark native features"
  > AWS Glue uses PySpark to include Python files in AWS Glue ETL jobs. You will want to use `--additional-python-modules` to manage your dependencies when available. You can use the `--extra-py-files` job parameter to include Python files. Dependencies must be hosted in Amazon S3 and the argument value should be a comma delimited list of Amazon S3 paths with no spaces. This functionality behaves like the Python dependency management you would use with Spark. For more information on Python dependency management in Spark, see Using [PySpark Native Features](https://spark.apache.org/docs/latest/api/python/tutorial/python_packaging.html#using-pyspark-native-features) page in Apache Spark documentation. `--extra-py-files` is useful in cases where your additional code is not packaged, or when you are migrating a Spark program with an existing toolchain for managing dependencies. For your dependency tooling to be maintainable, you will have to bundle your dependencies before submitting.
   * In short, `--extra-py-files` for AWS Glue corresponds to `--py-files` with vanilla Apache Spark

## OpenSearch Dashboards

[OpenSearch Dashboards](https://docs.opensearch.org/latest/dashboards/) "is the web UI for OpenSearch. You can use OpenSearch Dashboards to perform most tasks you can do with the OpenSearch APIs. You can also create visualizations and data dashboards with OpenSearch Dashboards."

* [OpenSearch > Docs > Creating dashboards](https://docs.opensearch.org/latest/dashboards/dashboard/index/)
  * Click the "Create" button and select the "Dashboard" on dropdown
    * Local URL: http://localhost:5601/app/dashboards#/create
* [OpenSearch > Docs > Observability](https://docs.opensearch.org/latest/observing-your-data/)
  * Click the "Create" button and select the "Observability Dashboard" on the dropdown
    * Local URL: http://localhost:5601/app/observability-dashboards#/create
* [OpenSearch Observability Stack](https://observability.opensearch.org/) – Stack built on top of OpenSearch, [Prometheus](https://prometheus.io/docs/introduction/overview/), and [OTLP](https://opentelemetry.io/docs/specs/otlp/) endpoint associated with [OpenSearch > Docs > OpenSearch Data Prepper](https://docs.opensearch.org/latest/data-prepper/)
  * [OpenSearch Observability Stack > Docs](https://observability.opensearch.org/docs/)

### OpenSearch Dashboards – Visualizations

[OpenSearch > Docs > Building data visualizations](https://docs.opensearch.org/latest/dashboards/visualize/index/) "provides two approaches for creating data visualizations: building visualizations visually and building visualizations using queries. Both produce charts that you can save and add to dashboards."

OpenSearch Dashboards has the following [visualization types](https://docs.opensearch.org/latest/dashboards/visualize/visualize-app/viz-types/):

| Visualization Category | Visualization Type | Description |
| -- | -- | -- |
| Text | [Metric visualizations]() | "Displays a single numeric value prominently. Use for KPIs and summary statistics." |
| Text | [Tag clouds](https://docs.opensearch.org/latest/dashboards/visualize/tag-cloud/) | "Displays words sized by frequency or another metric." |
| Text | [Data tables](https://docs.opensearch.org/latest/dashboards/visualize/data-table/) | "Displays raw or aggregated data in tabular form." |
| One-dimensional | [Gauge visualizations](https://docs.opensearch.org/latest/dashboards/visualize/gauge/) | "Displays a single value on a dial relative to defined ranges or thresholds." |
| One-dimensional | [Goal visualizations](https://docs.opensearch.org/latest/dashboards/visualize/goal/) | "Displays a single value on a progress bar relative to a target." |
| One-dimensional | [Pie charts](https://docs.opensearch.org/latest/dashboards/visualize/pie-charts/) | "Displays proportional data as slices of a circle. Use for part-to-whole comparisons." |
| Multidimensional | [Bar charts](https://docs.opensearch.org/latest/dashboards/visualize/bar-charts/) | "Compare categorical data as vertical or horizontal bars. Use for ranking or comparing values across categories." |
| Multidimensional | [Area charts](https://docs.opensearch.org/latest/dashboards/visualize/area/) | "Displays data as a filled region between a line and the axis. Use for showing volume over time or comparing stacked categories." |
| Multidimensional | [Heat maps](https://docs.opensearch.org/latest/dashboards/visualize/heat-map/) | "Uses color intensity to represent values across two categorical dimensions." |
| Multidimensional | [Line charts](https://docs.opensearch.org/latest/dashboards/visualize/line-charts/) | "Plots data points connected by lines. Use for visualizing trends and changes over time." |
| Map | [Coordinate maps](https://docs.opensearch.org/latest/dashboards/visualize/coordinate-maps/) | "Plots geographic data points on a map using latitude and longitude coordinates." |
| Map | [Region maps](https://docs.opensearch.org/latest/dashboards/visualize/region-maps/) | "Colors geographic regions by aggregated value. Supports custom GeoJSON vector maps." |
| Map | [Maps application](https://docs.opensearch.org/latest/dashboards/visualize/maps/) | "A standalone mapping tool with multiple layer types, tooltips, filters, and labels." |
| Utility | [Markdown visualizations](https://docs.opensearch.org/latest/dashboards/visualize/markdown/) | "Renders Markdown text alongside data visualizations for context and instructions." |
| Utility | [Controls](https://docs.opensearch.org/latest/dashboards/visualize/controls/) | "Adds interactive filter panels (dropdown lists or range sliders) to a dashboard." |
| Other | [PPL visualizations](https://docs.opensearch.org/latest/dashboards/visualize/ppl/) | "Creates visualizations by entering PPL queries directly." |
| Other | [TSVB visualizations](https://docs.opensearch.org/latest/dashboards/visualize/tsvb/) | "Creates detailed time-series visualizations with support for Area, Line, Metric, Gauge, Markdown, and Data Table types." |
| Other | [Vega visualizations](https://docs.opensearch.org/latest/dashboards/visualize/vega/) | "Uses the Vega and Vega-Lite declarative grammars for custom visualizations." |
| Other | [VisBuilder](https://docs.opensearch.org/latest/dashboards/visualize/timeline/) | "A drag-and-drop tool for creating visualizations without selecting a chart type in advance." |
| Other | [Timeline visualizations](https://docs.opensearch.org/latest/dashboards/visualize/timeline/) | "Uses a text-based expression syntax to create time-series visualizations." |
