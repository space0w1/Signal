# Kubernetes manifests (placeholder)

This directory is reserved for the eventual migration off `docker-compose.yml` once the
app is stable enough to move to the self-hosted cluster. Planned contents:

- `backend-deployment.yaml` / `backend-service.yaml`
- `frontend-deployment.yaml` / `frontend-service.yaml`
- `pvc.yaml` for the SQLite data volume (or a Postgres StatefulSet if the DB is migrated)
- `ingress.yaml`
