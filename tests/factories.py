"""
Factory classes for creating test data using factory_boy
"""
import factory
from django.contrib.auth import get_user_model
from core.models import User, ReferralLog, BillingLog
from scores.models import Score
from setlists.models import Setlist, SetlistItem


class UserFactory(factory.django.DjangoModelFactory):
    """Factory for creating User instances"""
    
    class Meta:
        model = User
        skip_postgeneration_save = True
    
    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.Sequence(lambda n: f"user{n}@example.com")
    plan = "solo"
    total_quota_mb = 200
    used_quota_mb = 0
    
    @factory.post_generation
    def password(obj, create, extracted, **kwargs):
        if create:
            obj.set_password(extracted or 'testpass123')
            obj.save()


class ScoreFactory(factory.django.DjangoModelFactory):
    """Factory for creating Score instances"""
    
    class Meta:
        model = Score
    
    user = factory.SubFactory(UserFactory)
    title = factory.Faker('sentence', nb_words=3)
    composer = factory.Faker('name')
    instrumentation = factory.Iterator(['Piano', 'Full Orchestra', 'String Quartet', 'Solo Violin'])
    s3_key = factory.LazyAttribute(lambda obj: f"{obj.user.id}/scores/test/original.pdf")
    size_bytes = factory.Faker('pyint', min_value=1024*1024, max_value=50*1024*1024)  # 1MB - 50MB
    mime = "application/pdf"
    pages = factory.Faker('pyint', min_value=1, max_value=100)
    tags = factory.List([
        factory.Faker('word') for _ in range(3)
    ])


class SetlistFactory(factory.django.DjangoModelFactory):
    """Factory for creating Setlist instances"""
    
    class Meta:
        model = Setlist
    
    user = factory.SubFactory(UserFactory)
    title = factory.Faker('sentence', nb_words=4)
    description = factory.Faker('text', max_nb_chars=200)


class SetlistItemFactory(factory.django.DjangoModelFactory):
    """Factory for creating SetlistItem instances"""
    
    class Meta:
        model = SetlistItem
    
    setlist = factory.SubFactory(SetlistFactory)
    score = factory.SubFactory(ScoreFactory)
    notes = factory.Faker('text', max_nb_chars=100)
    # order_index� �� `��\ �X� JL


class ReferralLogFactory(factory.django.DjangoModelFactory):
    """Factory for creating ReferralLog instances"""
    
    class Meta:
        model = ReferralLog
    
    user = factory.SubFactory(UserFactory)
    referred_user = factory.SubFactory(UserFactory)
    bonus_mb = 50


class BillingLogFactory(factory.django.DjangoModelFactory):
    """Factory for creating BillingLog instances"""
    
    class Meta:
        model = BillingLog
    
    user = factory.SubFactory(UserFactory)
    action = factory.Iterator(['upload', 'delete'])
    amount_mb = factory.Faker('pyint', min_value=1, max_value=100)
    description = factory.Faker('sentence')