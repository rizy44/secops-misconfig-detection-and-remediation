# Grafana verify
docker exec -it <grafana_container_id> curl http://prometheus:9090/api/v1/status/config
docker exec -it <grafana_container_id> curl http://loki:3100/ready
187a138fa20e1982edd2247793689329fc92323b0b2db30b4f1043c286b4ceb4
docker exec -it <grafana_container_id> curl http://prometheus:9090/api/v1/status/config
docker exec -it <grafana_container_id> curl http://loki:3100/ready
