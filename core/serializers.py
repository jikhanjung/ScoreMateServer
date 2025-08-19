"""
Serializers for core app (authentication, users)
"""
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from .models import User


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration"""
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = ('email', 'username', 'password', 'password_confirm', 'plan')
        extra_kwargs = {
            'plan': {'default': 'solo'},
        }
    
    def validate(self, attrs):
        """Validate password confirmation"""
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                'password_confirm': 'Password confirmation does not match.'
            })
        return attrs
    
    def validate_email(self, value):
        """Validate email uniqueness"""
        if User.objects.filter(email=value.lower()).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return value.lower()
    
    def validate_username(self, value):
        """Validate username uniqueness"""
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('A user with this username already exists.')
        return value
    
    def create(self, validated_data):
        """Create a new user with validated data"""
        # Remove password_confirm from validated_data
        validated_data.pop('password_confirm', None)
        
        # Create user using create_user to ensure proper password hashing
        user = User.objects.create_user(**validated_data)
        return user


class UserLoginSerializer(serializers.Serializer):
    """Serializer for user login"""
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    
    def validate(self, attrs):
        """Validate login credentials"""
        email = attrs.get('email')
        password = attrs.get('password')
        
        if email and password:
            # Authenticate using email (not username)
            user = authenticate(
                request=self.context.get('request'),
                username=email,  # Our User model uses email for authentication
                password=password
            )
            
            if not user:
                raise serializers.ValidationError(
                    'Invalid email or password.',
                    code='invalid_credentials'
                )
            
            if not user.is_active:
                raise serializers.ValidationError(
                    'User account is disabled.',
                    code='account_disabled'
                )
            
            attrs['user'] = user
            return attrs
        else:
            raise serializers.ValidationError(
                'Must include email and password.',
                code='missing_credentials'
            )


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile (read-only)"""
    available_quota_mb = serializers.ReadOnlyField()
    quota_usage_percentage = serializers.ReadOnlyField()
    
    class Meta:
        model = User
        fields = (
            'id', 'email', 'username', 'plan', 
            'total_quota_mb', 'used_quota_mb', 'available_quota_mb',
            'quota_usage_percentage', 'referral_code', 
            'date_joined', 'last_login'
        )
        read_only_fields = (
            'id', 'email', 'total_quota_mb', 'used_quota_mb',
            'referral_code', 'date_joined', 'last_login'
        )