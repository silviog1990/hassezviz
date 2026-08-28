# EZVIZ HP5 Gate Controller

Un'integrazione custom per Home Assistant che apre il relè del
cancello/porta di un videocitofono EZVIZ HP5 tramite le API cloud EZVIZ,
esposta come entità `lock` native — nessun servizio separato, nessun
`rest_command` necessario.

L'integrazione ufficiale EZVIZ di Home Assistant non espone entità
lock/unlock per questo dispositivo, e l'HP5 usa un formato di richiesta
diverso da quello atteso dal supporto unlock integrato di `pyezvizapi`.
Questa integrazione implementa direttamente il formato corretto.

## Installazione

### Tramite HACS (repository personalizzata)

1. In HACS, vai su **Integrazioni → ⋮ → Repository personalizzate**.
2. Aggiungi l'URL di questo repository, categoria **Integrazione**.
3. Installa "EZVIZ HP5 Gate Controller" da HACS.
4. Riavvia Home Assistant.

### Manuale

Copia `custom_components/ezviz_hp5` nella cartella `custom_components` di
Home Assistant, poi riavvia Home Assistant.

## Configurazione

Vai su **Impostazioni → Dispositivi e servizi → Aggiungi integrazione**,
cerca "EZVIZ HP5 Gate Controller" e inserisci:

- **Account EZVIZ** (email) e **password**
- **Numero di serie del dispositivo** — lo trovi nell'app EZVIZ:
  seleziona il tuo dispositivo HP5, tocca l'icona delle impostazioni
  (ingranaggio), poi "Informazioni dispositivo". È anche stampato
  sull'etichetta fisica/QR code sul retro del dispositivo.
- **URL API** (avanzato) — lascia il valore predefinito
  (`apiieu.ezvizlife.com`) a meno che il tuo account EZVIZ non sia
  registrato in una regione diversa.

Vengono create due entità `lock`: **Gate** e **Door**. Sbloccare invia il
comando a EZVIZ; l'entità torna a "locked" localmente dopo pochi secondi,
replicando il comportamento a impulso dell'elettroserratura fisica.
Bloccare manualmente (dalla UI) non invia alcun comando a EZVIZ.

Se la password EZVIZ cambia, Home Assistant chiederà di reinserire le
credenziali tramite una notifica di riparazione.

## Sicurezza

Le credenziali sono salvate nello storage delle config entry di Home
Assistant (`.storage`), mai in YAML e mai loggate.
