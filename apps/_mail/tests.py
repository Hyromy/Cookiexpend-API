import pytest
from django.core import mail

from .mails import send_mail


@pytest.mark.django_db
class TestSendMail:
    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        self.mock_render = mocker.patch(
            "apps._mail.mails.render_to_string",
            return_value="<html><body>Test Template {{ current_year }}</body></html>",
        )

    def test_send_mail_success(self, settings):
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

        ctx_data = {"user_name": "Carlos"}
        to = ["carlos@example.com"]
        subject = "Welcome to the System"
        template_path = "emails/welcome.html"

        send_mail(template=template_path, ctx=ctx_data, subject=subject, to=to)

        assert len(mail.outbox) == 1
        email = mail.outbox[0]

        assert email.subject == subject
        assert email.to == to
        assert "current_year" in ctx_data

        # Corregimos esta línea para usar el assert nativo de la herramienta de mock
        self.mock_render.assert_called_once_with(template_path, ctx_data)

    def test_send_mail_attaches_html_alternative(self, settings):
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        mail.outbox = []

        send_mail(
            template="emails/invoice.html",
            ctx={},
            subject="Your Invoice",
            to=["client@example.com"],
        )

        assert len(mail.outbox) == 1
        email = mail.outbox[0]

        assert len(email.alternatives) == 1
        contenido_html, tipo_mimetype = email.alternatives[0]
        assert tipo_mimetype == "text/html"
        assert "Test Template" in contenido_html
