# Generated migration to add structured auth fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("integrations", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="providercredential",
            name="auth_type",
            field=models.CharField(choices=[('json', 'JSON blob (legacy)'), ('oauth2', 'OAuth2 (Client ID & Secret)'), ('bearer', 'Bearer token')], default='json', max_length=20),
        ),
        migrations.AddField(
            model_name="providercredential",
            name="encrypted_client_id",
            field=models.TextField(blank=True, null=True, help_text='Fernet-encrypted client_id for OAuth2.'),
        ),
        migrations.AddField(
            model_name="providercredential",
            name="encrypted_client_secret",
            field=models.TextField(blank=True, null=True, help_text='Fernet-encrypted client_secret for OAuth2.'),
        ),
        migrations.AddField(
            model_name="providercredential",
            name="encrypted_bearer_token",
            field=models.TextField(blank=True, null=True, help_text='Fernet-encrypted bearer token.'),
        ),
        migrations.AlterField(
            model_name="providercredential",
            name="ciphertext",
            field=models.TextField(blank=True, null=True, help_text='Fernet-encrypted JSON blob — use set_credentials()/get_credentials(), never edit directly.'),
        ),
        migrations.AddField(
            model_name='providercredential',
            name='encrypted_metadata',
            field=models.TextField(blank=True, null=True, help_text='Fernet-encrypted JSON blob for provider metadata (e.g. whatsapp_number)'),
        ),
    ]
