from django.apps import AppConfig
class TeamBackendConfig(AppConfig):
    name='team_backend'
    verbose_name='LinkedIn Team'
    def ready(self):
        # A paid provider refusing its key alerts on Slack (alertas_slack); knowledge has no Django of its own.
        from knowledge import providers
        from .alertas_slack import provider_refused
        if provider_refused not in providers.CREDENTIAL_LISTENERS:providers.CREDENTIAL_LISTENERS.append(provider_refused)
        # Phase 6: her reply stops the sequence (secuencia_comprador._stop) and is traced for the reply step.
        from .respuesta_comprador import on_reply
        from .secuencia_comprador import REPLY_HANDLERS
        if on_reply not in REPLY_HANDLERS:REPLY_HANDLERS.append(on_reply)
