from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from localflavor.cz.forms import CZPostalCodeField

from .models import Order, ShopConfig


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


class CheckoutAddressForm(forms.Form):
    name = forms.CharField(max_length=255, widget=forms.TextInput(attrs={'class': 'form-control'}), label='Jméno a příjmení')
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control'}), label='E-mail')
    phone = forms.CharField(max_length=32, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}), label='Telefon')
    street = forms.CharField(max_length=255, widget=forms.TextInput(attrs={'class': 'form-control'}), label='Ulice a číslo domu')
    city = forms.CharField(max_length=128, widget=forms.TextInput(attrs={'class': 'form-control'}), label='Město')
    postal_code = CZPostalCodeField(widget=forms.TextInput(attrs={'class': 'form-control'}), label='PSČ')
    country = forms.CharField(max_length=64, initial='Česká republika', widget=forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly'}), label='Stát')
    is_company_order = forms.BooleanField(required=False, label='Nakupuji na firmu')
    company_name = forms.CharField(max_length=255, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}), label='Název firmy')
    company_id = forms.CharField(max_length=32, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}), label='IČO')
    vat_id = forms.CharField(max_length=32, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}), label='DIČ')

    def get_address(self):
        return f"{self.cleaned_data['street']}\n{self.cleaned_data['postal_code']} {self.cleaned_data['city']}\n{self.cleaned_data['country']}"

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('is_company_order') and not cleaned_data.get('company_name'):
            self.add_error('company_name', 'Pro nákup na firmu vyplňte název firmy.')
        return cleaned_data


class CheckoutShippingForm(forms.Form):
    shipping_method = forms.ChoiceField(
        choices=Order.SHIPPING_METHOD_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Způsob dopravy',
        initial=Order.SHIPPING_METHOD_ZASILKOVNA,
    )
    pickup_point_name = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Např. Zásilkovna Praha 4 - Budějovická'}),
        label='Výdejní místo / pobočka',
    )
    pickup_point_code = forms.CharField(
        max_length=128,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Interní kód výdejního místa'}),
        label='Kód výdejního místa',
    )

    def get_address(self):
        return f"{self.cleaned_data['street']}\n{self.cleaned_data['postal_code']} {self.cleaned_data['city']}\n{self.cleaned_data['country']}"

    def clean(self):
        cleaned_data = super().clean()
        shipping_method = cleaned_data.get('shipping_method')
        pickup_point_name = cleaned_data.get('pickup_point_name')

        if shipping_method in {Order.SHIPPING_METHOD_ZASILKOVNA, Order.SHIPPING_METHOD_BALIKOVNA} and not pickup_point_name:
            self.add_error('pickup_point_name', 'Pro výdejní místo doplňte název pobočky.')

        return cleaned_data


class CheckoutPaymentForm(forms.Form):
    payment_method = forms.ChoiceField(
        choices=Order.PAYMENT_METHOD_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Způsob platby',
        initial=Order.PAYMENT_METHOD_GOPAY,
    )


class CheckoutConfirmForm(forms.Form):
    agree_terms = forms.BooleanField(
        required=True,
        label='Souhlasím s obchodními podmínkami a zpracováním osobních údajů.',
    )
    register_account = forms.BooleanField(required=False, label='Vytvořit účet pro další nákup')
    account_password1 = forms.CharField(
        required=False,
        label='Heslo k účtu',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
    )
    account_password2 = forms.CharField(
        required=False,
        label='Heslo znovu',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
    )

    def clean(self):
        cleaned_data = super().clean()
        register_account = cleaned_data.get('register_account')
        password1 = cleaned_data.get('account_password1')
        password2 = cleaned_data.get('account_password2')

        if register_account:
            if not password1 or not password2:
                raise forms.ValidationError('Pro vytvoření účtu vyplňte obě hesla.')
            if password1 != password2:
                self.add_error('account_password2', 'Hesla se neshodují.')
            if password1 and len(password1) < 8:
                self.add_error('account_password1', 'Heslo musí mít alespoň 8 znaků.')

        return cleaned_data


class ReviewForm(forms.Form):
    rating = forms.ChoiceField(
        choices=[(str(i), f"{i} / 5") for i in range(5, 0, -1)],
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Hodnocení',
    )
    comment = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Napište recenzi ke knize...'}),
        label='Vaše recenze',
    )


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


class ShopConfigForm(forms.ModelForm):
    class Meta:
        model = ShopConfig
        fields = ['sender_email', 'service_email', 'shop_name', 'free_shipping_threshold', 'maintenance_mode', 'hide_zero_price_products']
        labels = {
            'sender_email': 'Odesílací e-mail',
            'service_email': 'Servisní email',
            'shop_name': 'Název obchodu',
            'free_shipping_threshold': 'Doprava zdarma od',
            'maintenance_mode': 'Režim údržby',
            'hide_zero_price_products': 'Skrýt produkty s nulovou cenou',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.pop('class', None)
