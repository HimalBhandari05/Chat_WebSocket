import uuid

from django.contrib.auth import get_user_model
from django.db import models
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

User = get_user_model()


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=128)
    online = models.ManyToManyField(to=User, blank=True)

    last_message = models.ForeignKey(
        "Message",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    def get_online_count(self):
        return self.online.count()

    def __str__(self):
        return f"{self.name} ({self.get_online_count()})"


class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    from_user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="messages_from_me"
    )
    to_user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="messages_to_me"
    )
    content = models.CharField(max_length=512)
    timestamp = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)

    def __str__(self):
        return f"From {self.from_user.username} to {self.to_user.username}: {self.content} [{self.timestamp}]"


# Keep last_message in sync
@receiver(post_save, sender=Message)
def _set_last_message_on_save(sender, instance, created, **kwargs):
    conv = instance.conversation
    if conv.last_message is None or instance.timestamp >= conv.last_message.timestamp:
        conv.last_message = instance
        conv.save(update_fields=["last_message"])


@receiver(post_delete, sender=Message)
def _update_last_message_on_delete(sender, instance, **kwargs):
    conv = instance.conversation
    if conv.last_message_id == instance.id:
        conv.last_message = conv.messages.order_by("-timestamp").first()
        conv.save(update_fields=["last_message"])
