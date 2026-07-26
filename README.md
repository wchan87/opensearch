# OpenSearch

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
