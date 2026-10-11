"""Tiny translation table (English, Spanish, French).

The language follows Anki's interface language; anything that is not
Spanish or French falls back to English.
"""

from __future__ import annotations

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "addon_name": "Background Sync",
        "menu_settings": "Background Sync…",
        "status_synced": "Synced with AnkiWeb at {time}",
        "status_checked": "Up to date with AnkiWeb (checked at {time})",
        "status_never": "No background sync yet in this session",
        "status_syncing": "Syncing with AnkiWeb…",
        "status_paused_until": "Paused until {time}",
        "status_paused_session": "Paused until Anki restarts",
        "status_disabled": "Automatic background sync is off",
        "status_error": "Last attempt failed at {time}: {error}",
        "status_stopped": "Automatic sync stopped after repeated errors: {error}. Use Sync now to try again.",
        "status_login": "Not logged in to AnkiWeb. Click Sync in the toolbar to log in.",
        "status_full_sync": "A full sync is required. Click here, then choose upload or download.",
        "next_in": "Next check in about {minutes} min.",
        "next_soon": "Next check in less than a minute.",
        "waiting_idle": "Waiting for a short pause in your activity.",
        "click_hint": "Click for options.",
        "action_sync_now": "Sync now",
        "action_pause_1h": "Pause for 1 hour",
        "action_pause_session": "Pause until Anki restarts",
        "action_resume": "Resume automatic sync",
        "action_settings": "Settings…",
        "action_resolve_full": "Resolve full sync…",
        "tooltip_synced": "Background Sync: synced with AnkiWeb",
        "tooltip_error": "Background Sync: sync failed ({error}). It will retry automatically.",
        "tooltip_login": "Background Sync: your AnkiWeb login has expired. Click Sync to log in again.",
        "tooltip_busy": "Background Sync: Anki is busy, try again in a moment.",
        "error_network": "no internet connection or AnkiWeb unreachable",
        "dlg_title": "Background Sync — Settings",
        "dlg_enabled": "Sync with AnkiWeb automatically in the background",
        "dlg_interval": "Sync every",
        "dlg_interval_suffix": " min",
        "dlg_idle": "Wait until Anki has been idle for",
        "dlg_idle_suffix": " s",
        "dlg_idle_help": "If you are studying when a sync is due, it waits until you stop for this long, so it never interrupts you.",
        "dlg_show_indicator": "Show the status in the top toolbar",
        "dlg_notify_errors": "Show a brief notice when a sync fails",
        "dlg_notify_success": "Show a brief notice after every sync",
        "dlg_notes": "Media follow Anki's “Sync audio and images too” preference. If AnkiWeb requires a full sync, Anki's usual dialog asks you what to do.",
    },
    "es": {
        "addon_name": "Background Sync",
        "menu_settings": "Background Sync…",
        "status_synced": "Sincronizado con AnkiWeb a las {time}",
        "status_checked": "Al día con AnkiWeb (verificado a las {time})",
        "status_never": "Aún no hubo sincronización en segundo plano en esta sesión",
        "status_syncing": "Sincronizando con AnkiWeb…",
        "status_paused_until": "En pausa hasta las {time}",
        "status_paused_session": "En pausa hasta que reinicies Anki",
        "status_disabled": "La sincronización automática está desactivada",
        "status_error": "El último intento falló a las {time}: {error}",
        "status_stopped": "La sincronización automática se detuvo tras varios errores: {error}. Usa Sincronizar ahora para reintentar.",
        "status_login": "No has iniciado sesión en AnkiWeb. Haz clic en Sincronizar en la barra para iniciar sesión.",
        "status_full_sync": "Se requiere una sincronización completa. Haz clic aquí y elige subir o descargar.",
        "next_in": "Próxima verificación en unos {minutes} min.",
        "next_soon": "Próxima verificación en menos de un minuto.",
        "waiting_idle": "Esperando una breve pausa en tu actividad.",
        "click_hint": "Haz clic para ver opciones.",
        "action_sync_now": "Sincronizar ahora",
        "action_pause_1h": "Pausar 1 hora",
        "action_pause_session": "Pausar hasta reiniciar Anki",
        "action_resume": "Reanudar la sincronización automática",
        "action_settings": "Configuración…",
        "action_resolve_full": "Resolver la sincronización completa…",
        "tooltip_synced": "Background Sync: sincronizado con AnkiWeb",
        "tooltip_error": "Background Sync: falló la sincronización ({error}). Se reintentará sola.",
        "tooltip_login": "Background Sync: tu sesión de AnkiWeb expiró. Haz clic en Sincronizar para volver a entrar.",
        "tooltip_busy": "Background Sync: Anki está ocupado, inténtalo en un momento.",
        "error_network": "sin conexión a internet o AnkiWeb no responde",
        "dlg_title": "Background Sync — Configuración",
        "dlg_enabled": "Sincronizar con AnkiWeb automáticamente en segundo plano",
        "dlg_interval": "Sincronizar cada",
        "dlg_interval_suffix": " min",
        "dlg_idle": "Esperar a que Anki esté inactivo durante",
        "dlg_idle_help": "Si estás estudiando cuando toca sincronizar, espera a que pares este tiempo, para no interrumpirte nunca.",
        "dlg_idle_suffix": " s",
        "dlg_show_indicator": "Mostrar el estado en la barra superior",
        "dlg_notify_errors": "Mostrar un aviso breve cuando falle una sincronización",
        "dlg_notify_success": "Mostrar un aviso breve después de cada sincronización",
        "dlg_notes": "Los archivos multimedia siguen la preferencia de Anki «Sincronizar también audio e imágenes». Si AnkiWeb exige una sincronización completa, el diálogo habitual de Anki te preguntará qué hacer.",
    },
    "fr": {
        "addon_name": "Background Sync",
        "menu_settings": "Background Sync…",
        "status_synced": "Synchronisé avec AnkiWeb à {time}",
        "status_checked": "À jour avec AnkiWeb (vérifié à {time})",
        "status_never": "Pas encore de synchronisation en arrière-plan dans cette session",
        "status_syncing": "Synchronisation avec AnkiWeb…",
        "status_paused_until": "En pause jusqu'à {time}",
        "status_paused_session": "En pause jusqu'au redémarrage d'Anki",
        "status_disabled": "La synchronisation automatique est désactivée",
        "status_error": "La dernière tentative a échoué à {time} : {error}",
        "status_stopped": "Synchronisation automatique arrêtée après plusieurs erreurs : {error}. Utilisez Synchroniser maintenant pour réessayer.",
        "status_login": "Vous n'êtes pas connecté à AnkiWeb. Cliquez sur Synchroniser dans la barre pour vous connecter.",
        "status_full_sync": "Une synchronisation complète est requise. Cliquez ici, puis choisissez envoyer ou télécharger.",
        "next_in": "Prochaine vérification dans environ {minutes} min.",
        "next_soon": "Prochaine vérification dans moins d'une minute.",
        "waiting_idle": "En attente d'une courte pause dans votre activité.",
        "click_hint": "Cliquez pour les options.",
        "action_sync_now": "Synchroniser maintenant",
        "action_pause_1h": "Mettre en pause 1 heure",
        "action_pause_session": "Mettre en pause jusqu'au redémarrage d'Anki",
        "action_resume": "Reprendre la synchronisation automatique",
        "action_settings": "Paramètres…",
        "action_resolve_full": "Résoudre la synchronisation complète…",
        "tooltip_synced": "Background Sync : synchronisé avec AnkiWeb",
        "tooltip_error": "Background Sync : échec de la synchronisation ({error}). Nouvel essai automatique.",
        "tooltip_login": "Background Sync : votre connexion AnkiWeb a expiré. Cliquez sur Synchroniser pour vous reconnecter.",
        "tooltip_busy": "Background Sync : Anki est occupé, réessayez dans un instant.",
        "error_network": "pas de connexion internet ou AnkiWeb injoignable",
        "dlg_title": "Background Sync — Paramètres",
        "dlg_enabled": "Synchroniser automatiquement avec AnkiWeb en arrière-plan",
        "dlg_interval": "Synchroniser toutes les",
        "dlg_interval_suffix": " min",
        "dlg_idle": "Attendre qu'Anki soit inactif pendant",
        "dlg_idle_suffix": " s",
        "dlg_idle_help": "Si vous révisez au moment prévu, la synchronisation attend que vous fassiez une pause de cette durée, pour ne jamais vous interrompre.",
        "dlg_show_indicator": "Afficher l'état dans la barre d'outils",
        "dlg_notify_errors": "Afficher un bref avis quand une synchronisation échoue",
        "dlg_notify_success": "Afficher un bref avis après chaque synchronisation",
        "dlg_notes": "Les médias suivent la préférence d'Anki « Synchroniser aussi l'audio et les images ». Si AnkiWeb exige une synchronisation complète, la fenêtre habituelle d'Anki vous demande quoi faire.",
    },
}


def _lang() -> str:
    try:
        import anki.lang

        code = (anki.lang.current_lang or "en").lower()
    except Exception:
        code = "en"
    code = code.replace("-", "_").split("_")[0]
    return code if code in STRINGS else "en"


def t(key: str, **kwargs: object) -> str:
    """Return the translated string for ``key``, formatted with ``kwargs``."""
    text = STRINGS[_lang()].get(key) or STRINGS["en"].get(key, key)
    try:
        return text.format(**kwargs)
    except Exception:
        return text
