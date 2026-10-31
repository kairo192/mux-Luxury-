# Procédure de Sauvegarde & Plan de Reprise d'Activité (PRA / Disaster Recovery)

## 1. Politique de Sauvegarde Automatisée
- **Base PostgreSQL** : `pg_dump --format=custom` quotidien à 03h00, compressé et chiffré avec `gpg --symmetric --cipher-algo AES256`.
- **Médias & Images Produits** : Archive incrémentale de `/var/lib/luxe/uploads` avec calcul d'empreinte `SHA-256`.
- **Destination Externe** : Synchronisation vers un stockage hors-VPS (second serveur ou stockage objet S3-compatible) via `infrastructure/backups/backup_postgres_and_media.sh`.

## 2. Restauration sur un Nouveau VPS Algérien
```bash
./infrastructure/backups/restore_backup.sh /chemin/vers/luxe_backup_YYYYMMDD.sql.gz.gpg
```
