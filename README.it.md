# hassezviz (in precedenza "EZVIZ HP5 Gate Controller")

Un'integrazione custom per Home Assistant per dispositivi EZVIZ che
l'integrazione ufficiale non copre bene:

- **Videocitofono EZVIZ HP5** — apre il relè del cancello/porta tramite le
  API cloud EZVIZ, esposto come entità `lock` native (nessun servizio
  separato, nessun `rest_command` necessario).
- **Camere PTZ EZVIZ (es. CB8 Lite)** — elenca i preset della camera e li
  richiama da Home Assistant, così puoi creare un pattugliamento anche con
  camere a batteria.

L'integrazione ufficiale EZVIZ di Home Assistant non espone entità
lock/unlock per questo dispositivo, e l'HP5 usa un formato di richiesta
diverso da quello atteso dal supporto unlock integrato di `pyezvizapi`.
Questa integrazione implementa direttamente il formato corretto.

## Installazione

### Tramite HACS (repository personalizzata)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=silviog1990&repository=hassezviz&category=integration)

Clicca sul badge sopra per aggiungere questo repository a HACS sulla tua istanza, oppure fallo manualmente:

1. In HACS, vai su **Integrazioni → ⋮ → Repository personalizzate**.
2. Aggiungi `https://github.com/silviog1990/hassezviz`, categoria **Integrazione**.
3. Installa "hassezviz" (in precedenza "EZVIZ HP5 Gate Controller") da HACS.
4. Riavvia Home Assistant.

### Manuale

Copia `custom_components/ezviz_hp5` nella cartella `custom_components` di
Home Assistant, poi riavvia Home Assistant.

## Configurazione

Vai su **Impostazioni → Dispositivi e servizi → Aggiungi integrazione**,
cerca "hassezviz" (in precedenza "EZVIZ HP5 Gate Controller") e inserisci:

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

## Camera PTZ: pulsanti preset e pattugliamento (es. CB8 Lite)

Scegli **Camera PTZ** come tipo di dispositivo quando aggiungi
l'integrazione. L'integrazione legge i preset salvati sulla camera
nell'app EZVIZ e crea un `button` per ogni preset (con lo stesso nome) più
un pulsante **Refresh presets**. Premendo un pulsante la camera si sposta
su quel preset. Dopo aver aggiunto, rinominato o cancellato preset
nell'app EZVIZ, premi **Refresh presets** (o ricarica l'integrazione).

Un pattugliamento — utile per le camere a batteria che non lo supportano
da sole — è un semplice script o automazione:

```yaml
script:
  camera_patrol:
    sequence:
      - action: button.press
        target: {entity_id: button.ezviz_ptz_camera_xxx_ingresso}
      - delay: "00:00:20"
      - action: button.press
        target: {entity_id: button.ezviz_ptz_camera_xxx_giardino}
      - delay: "00:00:20"
      - action: button.press
        target: {entity_id: button.ezviz_ptz_camera_xxx_strada}
```

Limiti: solo cloud; supportato solo il canale 1; verificato solo sulla
CB8 Lite; i preset si creano nell'app EZVIZ. Se il tuo account EZVIZ non è
sul server europeo, imposta di conseguenza l'**URL API**.

## Sicurezza

Le credenziali sono salvate nello storage delle config entry di Home
Assistant (`.storage`), mai in YAML e mai loggate.
