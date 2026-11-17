from django.apps import AppConfig
class TeamBackendConfig(AppConfig):
    name='team_backend'
    verbose_name='LinkedIn Team'
    def ready(self):
        # A paid provider refusing its key alerts on Slack (alertas_slack); knowledge has no Django of its own.
        from knowledge import providers
        from .alertas_slack import provider_refused
        if provider_refused not in providers.CREDENTIAL_LISTENERS:providers.CREDENTIAL_LISTENERS.append(provider_refused)
