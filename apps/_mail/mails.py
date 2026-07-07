from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils.timezone import now


def send_mail(*, template: str, ctx: dict[str, str], subject: str, to: list[str]):
    ctx["current_year"] = now().year
    
    html_content = render_to_string(template, ctx)

    email = EmailMultiAlternatives(
        subject=subject,
        body=strip_tags(html_content),
        from_email=None,
        to=to,
    )
    email.attach_alternative(html_content, "text/html")

    email.send(fail_silently=False)
