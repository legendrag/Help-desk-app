import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from webpush.forms import WebPushForm, SubscriptionForm
from webpush.views import process_subscription_data
import copy

post_data = {
    "status_type": "subscribe",
    "subscription": {
        "endpoint": "https://fcm.googleapis.com/fcm/send/123",
        "expirationTime": None,
        "keys": {
            "p256dh": "p256dh_value",
            "auth": "auth_value"
        }
    },
    "browser": "chrome"
}

subscription_data = process_subscription_data(copy.deepcopy(post_data))
print("subscription_data:", subscription_data)
subscription_form = SubscriptionForm(subscription_data)
print("subscription_form valid?", subscription_form.is_valid())
if not subscription_form.is_valid():
    print("subscription_form errors:", subscription_form.errors)

# simulate post_data after process_subscription_data pop
# post_data is passed to process_subscription_data, which pops 'subscription', 'browser'
mutated_post_data = {
    "status_type": "subscribe",
}

web_push_form = WebPushForm(mutated_post_data)
print("web_push_form valid?", web_push_form.is_valid())
if not web_push_form.is_valid():
    print("web_push_form errors:", web_push_form.errors)
