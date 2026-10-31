# Guide de Déploiement en Production — Serveur VPS en Algérie

## 1. Évaluation des Hébergeurs VPS en Algérie

L'architecture Docker Compose est 100% portable et compatible avec les principaux fournisseurs disposant de datacenters physiques en Algérie :

| Critère | ICOSNET (Alger) | ISSAL NET (Alger) | HOSTARTS (Algérie) |
| :--- | :--- | :--- | :--- |
| **Localisation physique** | Algérie (Alger) | Algérie (Alger) | Algérie |
| **Compatibilité Ubuntu LTS & Docker** | Oui (KVM / Accès Root SSH) | Oui (KVM / Accès Root SSH) | Oui |
| **Spécification initiale recommandée** | 4 vCPU, 8 Go RAM, 120 Go NVMe, IPv4 publique | 4 vCPU, 8 Go RAM, 120 Go SSD, IPv4 publique | 4 vCPU, 8 Go RAM, 100 Go NVMe |

## 2. Procédure d'installation sur Ubuntu 22.04 / 24.04 LTS

```bash
# 1. Durcissement SSH & Pare-feu UFW
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# 2. Cloner le dépôt et configurer les variables d'environnement
git clone https://github.com/kairo192/mux-Luxury-.git
cd mux-Luxury-
cp .env.example .env
nano .env # Renseigner POSTGRES_PASSWORD, SECRET_KEY, WHATSAPP_CLOUD_API_TOKEN

# 3. Lancer la pile de production
docker compose up -d --build
```
