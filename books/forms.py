from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from localflavor.cz.forms import CZPostalCodeField


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user


class CheckoutForm(forms.Form):
    name = forms.CharField(max_length=255, widget=forms.TextInput(attrs={'class': 'form-control'}), label='Jméno a příjmení')
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control'}), label='E-mail')
    street = forms.CharField(max_length=255, widget=forms.TextInput(attrs={'class': 'form-control'}), label='Ulice a číslo domu')
    city = forms.CharField(max_length=128, widget=forms.TextInput(attrs={'class': 'form-control'}), label='Město')
    postal_code = CZPostalCodeField(widget=forms.TextInput(attrs={'class': 'form-control'}), label='PSČ')
    country = forms.CharField(max_length=64, initial='Česká republika', widget=forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly'}), label='Stát')

    def get_address(self):
        return f"{self.cleaned_data['street']}\n{self.cleaned_data['postal_code']} {self.cleaned_data['city']}\n{self.cleaned_data['country']}"


class ContactForm(forms.Form):
    TOPIC_CHOICES = [
        ('recommendation', 'Doporučení knihy'),
        ('order_status', 'Stav objednávky'),
        ('technical', 'Technická podpora'),
        ('general', 'Obecný dotaz'),
    ]

    name = forms.CharField(max_length=255, widget=forms.TextInput(attrs={'class': 'form-control'}), label='Jméno')
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control'}), label='E-mail')
    topic = forms.ChoiceField(choices=TOPIC_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}), label='O čem chcete mluvit')
    message = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 6,
            'placeholder': 'Napište nám svůj dotaz. Například: Rád/a bych doporučení na nové fantasy, které je vhodné pro dárkový výběr.'
        }),
        label='Váš dotaz',
    )


from .models import ShopConfig


class ShopConfigForm(forms.ModelForm):
    class Meta:
        model = ShopConfig
        fields = ['service_email', 'shop_name', 'maintenance_mode', 'hide_zero_price_products']
        labels = {
            'service_email': 'Servisní email',
            'shop_name': 'Název obchodu',
            'maintenance_mode': 'Režim údržby',
            'hide_zero_price_products': 'Skrýt produkty s nulovou cenou',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.pop('class', None)
