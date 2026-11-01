# Configuration Tunnel Sécurisé WireGuard — Mus Luxury (LUXE)

Ce tunnel chiffré isole le **CMS Bureau Windows** du trafic internet public :

```
[ PC Windows Bureau (Tauri 2) ]  ---( Tunnel WireGuard Chiffré ChaCha20-Poly1305 )--->  [ VPS Algérien (10.8.0.1) ]
         IP: 10.8.0.2                                                                       Nginx / FastAPI / PostgreSQL
```

- **Chiffrement** : ChaCha20-Poly1305, Curve25519, BLAKE2s (standards cryptographiques les plus stricts).
- **Isolation** : L'API `/api/v1/admin/*` peut être configurée pour écouter uniquement sur `10.8.0.1:8000`, la rendant **invisible et inaccessible** depuis l'Internet public.
