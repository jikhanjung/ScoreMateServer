"""
웹 폼 — 규칙은 API 와 같은 곳(scores/services.py · ensembles/services.py · 모델 권한)에 있고 여기는 입력만 다룬다
"""
from pathlib import Path

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

from ensembles.models import Ensemble, Membership, Invite
from scores.models import Score

User = get_user_model()


class LoginForm(forms.Form):
    email = forms.EmailField(label='이메일', widget=forms.EmailInput(attrs={'autofocus': True, 'autocomplete': 'email'}))
    password = forms.CharField(label='비밀번호', widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}))


class RegisterForm(forms.Form):
    email = forms.EmailField(label='이메일', widget=forms.EmailInput(attrs={'autocomplete': 'email'}))
    username = forms.CharField(label='이름', max_length=150, help_text='멤버 목록에 보이는 이름')
    password1 = forms.CharField(label='비밀번호', widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}))
    password2 = forms.CharField(label='비밀번호 확인', widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}))

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('이미 가입된 이메일입니다.')
        return email

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('이미 쓰는 이름입니다.')
        return username

    def clean(self):
        data = super().clean()
        if data.get('password1') and data.get('password1') != data.get('password2'):
            self.add_error('password2', '비밀번호가 서로 다릅니다.')
        elif data.get('password1'):
            try:
                validate_password(data['password1'], User(email=data.get('email'), username=data.get('username')))
            except forms.ValidationError as e:
                self.add_error('password1', e)
        return data


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', MultipleFileInput(attrs={'accept': 'application/pdf,.pdf'}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single = super().clean
        if isinstance(data, (list, tuple)):
            return [single(d, initial) for d in data]
        return [single(data, initial)]


def managed_ensembles(user):
    """이 사람이 악보를 올릴 수 있는 앙상블 (owner · leader)"""
    return Ensemble.objects.filter(memberships__user=user, memberships__role__in=Membership.MANAGER_ROLES).order_by('name')


class UploadForm(forms.Form):
    files = MultipleFileField(label='PDF 파일', help_text='여러 파일을 한 번에 고를 수 있습니다.')
    ensemble = forms.ModelChoiceField(label='올릴 곳', queryset=Ensemble.objects.none(), required=False,
                                      empty_label='내 악보 (나만 보기)')
    title = forms.CharField(label='제목', max_length=255, required=False,
                            help_text='비우면 파일 이름. 여러 파일에 제목을 주면 각 파일 이름이 파트가 됩니다 (예: 블타바 + "Guitar 1.pdf").')
    part_name = forms.CharField(label='파트', max_length=100, required=False, help_text='예: 총보, Guitar 1')
    composer = forms.CharField(label='작곡 · 편곡', max_length=255, required=False)
    instrumentation = forms.CharField(label='편성', max_length=255, required=False)
    tags = forms.CharField(label='태그', max_length=500, required=False, help_text='쉼표로 나눕니다.')
    note = forms.CharField(label='메모', required=False, widget=forms.Textarea(attrs={'rows': 3}))

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields['ensemble'].queryset = managed_ensembles(user)

    def clean_files(self):
        files = self.cleaned_data['files']
        total = 0
        for f in files:
            if f.size > settings.MAX_UPLOAD_SIZE:
                raise forms.ValidationError(
                    f'{f.name}: 파일이 너무 큽니다 (최대 {settings.MAX_UPLOAD_SIZE // (1024 * 1024)}MB).')
            head = f.read(5)
            f.seek(0)
            if head != b'%PDF-':
                raise forms.ValidationError(f'{f.name}: PDF 파일이 아닙니다.')
            total += f.size
        if not self.user.can_upload(total):
            raise forms.ValidationError(f'저장 공간이 부족합니다 (남은 공간 {self.user.available_quota_mb}MB).')
        return files

    def items(self):
        """(파일, 제목, 파트) — 여러 파일이면 제목이 곡 이름, 파일 이름이 파트"""
        files = self.cleaned_data['files']
        title = self.cleaned_data['title'].strip()
        part = self.cleaned_data['part_name'].strip()
        for f in files:
            stem = Path(f.name).stem
            if len(files) > 1 and title:
                yield f, title, part or stem
            else:
                yield f, title or stem, part

    def tag_list(self):
        return [t.strip() for t in self.cleaned_data['tags'].split(',') if t.strip()][:30]


class ScoreEditForm(forms.ModelForm):
    tags_text = forms.CharField(label='태그', max_length=500, required=False, help_text='쉼표로 나눕니다.')

    class Meta:
        model = Score
        fields = ['title', 'part_name', 'composer', 'instrumentation', 'note']
        labels = {'title': '제목', 'part_name': '파트', 'composer': '작곡 · 편곡', 'instrumentation': '편성', 'note': '메모'}
        widgets = {'note': forms.Textarea(attrs={'rows': 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tags_text'].initial = ', '.join(self.instance.tags or [])

    def save(self, commit=True):
        self.instance.tags = [t.strip() for t in self.cleaned_data['tags_text'].split(',') if t.strip()][:30]
        return super().save(commit)


class EnsembleForm(forms.ModelForm):
    class Meta:
        model = Ensemble
        fields = ['name', 'description']
        labels = {'name': '이름', 'description': '소개'}
        widgets = {'description': forms.Textarea(attrs={'rows': 2})}


class MemberForm(forms.Form):
    role = forms.ChoiceField(label='역할', choices=Membership.ROLE_CHOICES, required=False)
    part = forms.CharField(label='파트', max_length=100, required=False)


EXPIRY_CHOICES = [('1', '1일'), ('7', '7일'), ('30', '30일'), ('', '만료 없음')]


class InviteForm(forms.Form):
    expires_in_days = forms.ChoiceField(label='유효 기간', choices=EXPIRY_CHOICES, initial=str(Invite.DEFAULT_EXPIRY_DAYS), required=False)
    max_uses = forms.IntegerField(label='최대 인원', min_value=1, max_value=1000, required=False, help_text='비우면 제한 없음')

    def days(self):
        value = self.cleaned_data.get('expires_in_days')
        return int(value) if value else None


class JoinCodeForm(forms.Form):
    code = forms.CharField(label='초대 코드', max_length=32, widget=forms.TextInput(attrs={'autocapitalize': 'characters', 'autocomplete': 'off'}))


class NewVersionForm(forms.Form):
    file = forms.FileField(label='새 판 PDF', widget=forms.ClearableFileInput(attrs={'accept': 'application/pdf,.pdf'}))
    note = forms.CharField(label='무엇이 바뀌었나', max_length=2000, required=False,
                           widget=forms.TextInput(attrs={'placeholder': '예: 42쪽까지 수정, 도돌이 풀기'}))

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_file(self):
        f = self.cleaned_data['file']
        if f.size > settings.MAX_UPLOAD_SIZE:
            raise forms.ValidationError(f'파일이 너무 큽니다 (최대 {settings.MAX_UPLOAD_SIZE // (1024 * 1024)}MB).')
        head = f.read(5)
        f.seek(0)
        if head != b'%PDF-':
            raise forms.ValidationError('PDF 파일이 아닙니다.')
        if not self.user.can_upload(f.size):
            raise forms.ValidationError(f'저장 공간이 부족합니다 (남은 공간 {self.user.available_quota_mb}MB).')
        return f


class ActivateForm(forms.Form):
    code = forms.CharField(label='TV 에 보이는 코드', max_length=16,
                           widget=forms.TextInput(attrs={'placeholder': 'BCDF-GHJK', 'autocapitalize': 'characters',
                                                         'autocomplete': 'off', 'autofocus': True,
                                                         'class': 'code', 'inputmode': 'text'}))


class DeviceNameForm(forms.Form):
    name = forms.CharField(label='기기 이름', max_length=100)


class SetlistForm(forms.Form):
    title = forms.CharField(label='이름', max_length=255, widget=forms.TextInput(attrs={'placeholder': '예: 2026 가을 연주회'}))
    description = forms.CharField(label='설명', required=False, widget=forms.Textarea(attrs={'rows': 2}))
    ensemble = forms.ModelChoiceField(label='어디의 곡목', queryset=Ensemble.objects.none(), required=False,
                                      empty_label='내 세트리스트 (나만 보기)')

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['ensemble'].queryset = managed_ensembles(user)
