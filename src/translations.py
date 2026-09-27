"""
UI text for the PySide6 front-end, in English and Spanish.

Kept separate from ytdlp_qt_gui so the widget code stays readable. Nothing
here talks to Qt or ytdlp_core; it is just string tables and a lookup helper.
"""

LANGUAGES = {
    "en": "English",
    "es": "Español",
}

DEFAULT_LANGUAGE = "en"

TRANSLATIONS = {
    "en": {
        "window_title": "yt-dlp GUI",
        "tab_download": "Download",
        "tab_settings": "Settings",
        "download_type_label": "Download type",
        "radio_audio": "Audio (MP3)",
        "radio_video": "Video (MP4)",
        "quality_label": "Quality",
        "quality_tooltip": (
            "Picks the best format up to that height. A video that does not "
            "reach it is downloaded at the closest quality below."
        ),
        "advanced_label": "Advanced",
        "format_placeholder": "Format codes, e.g. 299+140",
        "format_tooltip": "Overrides the quality preset when filled in.",
        "split_chapters_label": "Split into tracks using the chapters/timestamps of the video",
        "split_chapters_tooltip": "If the video has no chapters, it is downloaded normally.",
        "playlist_label": "Download the whole playlist",
        "playlist_tooltip": "Off: only the video itself, even if the link points into a playlist.",
        "url_label": "URL",
        "url_placeholder": "Enter video URL",
        "filename_label": "Output filename (optional)",
        "filename_placeholder": "Leave empty to keep the video title name",
        "folder_label": "Download folder",
        "browse_button": "Browse",
        "command_label": "Custom command (optional)",
        "command_placeholder": "Write a full command to run it as-is, ignoring the options above",
        "output_label": "Output",
        "download_button": "Download",
        "list_formats_button": "List formats",
        "stop_button": "Stop",
        "working": "Working...",
        "theme_label": "Theme",
        "theme_dark": "Dark",
        "theme_light": "Light",
        "advanced_features_label": "Advanced Features",
        "allow_advanced_features_label": "Allow advanced features",
        "allow_advanced_features_tooltip": (
            "Shows extra options in the Download tab: a custom command box, raw "
            "format codes, chapter splitting and whole-playlist downloads."
        ),
        "language_label": "Language",
        "error_title": "Error",
        "error_ytdlp_not_found": "yt-dlp was not found next to this script or on PATH",
        "warning_ffmpeg_missing": (
            "⚠ ffmpeg was not found. Audio extraction, merging and chapter "
            "splitting will not work until it is installed."
        ),
        "warning_ffprobe_missing": (
            "⚠ ffprobe was not found. Some downloads may fail until it is installed."
        ),
        "warning_ffmpeg_ffprobe_missing": (
            "⚠ ffmpeg and ffprobe were not found. Audio extraction, merging and "
            "chapter splitting will not work until they are installed."
        ),
        "log_stopping": "\n--- Stopping ---\n",
        "log_updating": "--- Updating yt-dlp ---\n",
        "log_listing_formats": "\nListing formats...\n",
        "log_download_started": "\n--- Download started ---\n",
        "log_split_chapters": "Splitting by chapters (plain download if the video has none)...\n",
        "log_ffmpeg_missing": (
            "Warning: ffmpeg was not found. Audio extraction, merging and "
            "chapter splitting need it and will fail.\n"
        ),
        "log_custom_command": "\n--- Running custom command ---\n",
        "status_stopped": "\n--- Stopped ---\n",
        "status_success": "\n--- Finished ---\n",
        "status_failed": "\n--- Failed (exit code {code}) ---\n",
        "status_error": "\n--- Could not run: {error} ---\n",
        "quality_not_selected": "Not selected (list formats)",
        "quality_best": "Best available",
        "quality_2160p": "4K (2160p)",
        "quality_1440p": "2K (1440p)",
        "quality_1080p": "1080p",
        "quality_720p": "720p",
        "quality_480p": "480p",
        "quality_smallest": "Smallest",
    },
    "es": {
        "window_title": "yt-dlp GUI",
        "tab_download": "Descargar",
        "tab_settings": "Ajustes",
        "download_type_label": "Tipo de descarga",
        "radio_audio": "Audio (MP3)",
        "radio_video": "Video (MP4)",
        "quality_label": "Calidad",
        "quality_tooltip": (
            "Elige el mejor formato hasta esa altura. Si el video no llega a "
            "ella, se descarga en la calidad más cercana por debajo."
        ),
        "advanced_label": "Avanzado",
        "format_placeholder": "Códigos de formato, p. ej. 299+140",
        "format_tooltip": "Sustituye a la calidad seleccionada si se rellena.",
        "split_chapters_label": "Dividir en pistas usando los capítulos/marcas de tiempo del video",
        "split_chapters_tooltip": "Si el video no tiene capítulos, se descarga normalmente.",
        "playlist_label": "Descargar toda la lista de reproducción",
        "playlist_tooltip": "Desactivado: solo el video, aunque el enlace pertenezca a una lista.",
        "url_label": "URL",
        "url_placeholder": "Introduce la URL del video",
        "filename_label": "Nombre de archivo de salida (opcional)",
        "filename_placeholder": "Déjalo vacío para usar el título del video",
        "folder_label": "Carpeta de descarga",
        "browse_button": "Examinar",
        "command_label": "Comando personalizado (opcional)",
        "command_placeholder": "Escribe un comando completo para ejecutarlo tal cual, ignorando las opciones anteriores",
        "output_label": "Salida",
        "download_button": "Descargar",
        "list_formats_button": "Listar formatos",
        "stop_button": "Detener",
        "working": "Trabajando...",
        "theme_label": "Tema",
        "theme_dark": "Oscuro",
        "theme_light": "Claro",
        "advanced_features_label": "Funciones avanzadas",
        "allow_advanced_features_label": "Permitir funciones avanzadas",
        "allow_advanced_features_tooltip": (
            "Muestra opciones adicionales en la pestaña Descargar: un comando "
            "personalizado, códigos de formato, división por capítulos y "
            "descarga de listas de reproducción completas."
        ),
        "language_label": "Idioma",
        "error_title": "Error",
        "error_ytdlp_not_found": "No se ha encontrado yt-dlp junto a este script ni en el PATH",
        "warning_ffmpeg_missing": (
            "⚠ No se ha encontrado ffmpeg. La extracción de audio, la fusión y "
            "la división por capítulos no funcionarán hasta que se instale."
        ),
        "warning_ffprobe_missing": (
            "⚠ No se ha encontrado ffprobe. Algunas descargas pueden fallar hasta que se instale."
        ),
        "warning_ffmpeg_ffprobe_missing": (
            "⚠ No se han encontrado ffmpeg ni ffprobe. La extracción de audio, la "
            "fusión y la división por capítulos no funcionarán hasta que se instalen."
        ),
        "log_stopping": "\n--- Deteniendo ---\n",
        "log_updating": "--- Actualizando yt-dlp ---\n",
        "log_listing_formats": "\nListando formatos...\n",
        "log_download_started": "\n--- Descarga iniciada ---\n",
        "log_split_chapters": "Dividiendo por capítulos (descarga normal si el video no tiene)...\n",
        "log_ffmpeg_missing": (
            "Aviso: no se ha encontrado ffmpeg. La extracción de audio, la "
            "fusión y la división por capítulos lo necesitan y fallarán.\n"
        ),
        "log_custom_command": "\n--- Ejecutando comando personalizado ---\n",
        "status_stopped": "\n--- Detenido ---\n",
        "status_success": "\n--- Finalizado ---\n",
        "status_failed": "\n--- Fallido (código de salida {code}) ---\n",
        "status_error": "\n--- No se pudo ejecutar: {error} ---\n",
        "quality_not_selected": "No seleccionada (listar formatos)",
        "quality_best": "Mejor disponible",
        "quality_2160p": "4K (2160p)",
        "quality_1440p": "2K (1440p)",
        "quality_1080p": "1080p",
        "quality_720p": "720p",
        "quality_480p": "480p",
        "quality_smallest": "Más pequeña",
    },
}

# core.QUALITY_LABELS (English, used as dict keys in ytdlp_core) -> translation key
QUALITY_LABEL_KEYS = {
    "Not selected (list formats)": "quality_not_selected",
    "Best available": "quality_best",
    "4K (2160p)": "quality_2160p",
    "2K (1440p)": "quality_1440p",
    "1080p": "quality_1080p",
    "720p": "quality_720p",
    "480p": "quality_480p",
    "Smallest": "quality_smallest",
}


def tr(language, key, **kwargs):
    """The text for `key` in `language`, falling back to English."""
    text = TRANSLATIONS.get(language, TRANSLATIONS[DEFAULT_LANGUAGE]).get(
        key, TRANSLATIONS[DEFAULT_LANGUAGE][key]
    )
    return text.format(**kwargs) if kwargs else text
