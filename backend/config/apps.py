from django.apps import AppConfig


class ConfigConfig(AppConfig):
    name = "config"
    verbose_name = "PMS Config"

    def ready(self):
        try:
            from unfold.templatetags import unfold as unfold_tags

            def _safe_flatten_context(context):
                flat = {}
                for mapping in getattr(context, "dicts", []):
                    if hasattr(mapping, "items"):
                        flat.update(mapping)
                return flat

            unfold_tags._flatten_context = _safe_flatten_context
        except Exception:
            pass
