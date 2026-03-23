"""
Forms for procurement timeline and method selection.
"""
from django import forms
from apps.procurement.timeline_utils import PUBLICATION_TIMELINES


class ProcurementMethodForm(forms.Form):
    """
    Form for selecting procurement method.
    Used when entering stages that require method selection (e.g., Publication of TD).
    """
    procurement_method = forms.ChoiceField(
        label='Procurement Method',
        choices=[('', '-- Select Procurement Method --')] + [
            (method, method) for method in sorted(PUBLICATION_TIMELINES.keys())
        ],
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'procurementMethod',
            'required': True
        }),
        help_text='Select the procurement method that will determine the publication timeline.'
    )


class BidValidityExtensionForm(forms.Form):
    """
    Form for extending bid validity period.
    Shows confirmation before extending by 60 days.
    """
    confirm_extension = forms.BooleanField(
        label='I confirm extending the bid validity period by 60 additional business days',
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'confirmExtension',
        })
    )
    extension_reason = forms.CharField(
        label='Reason for Extension',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Explain why the bid validity period needs to be extended',
            'required': True
        }),
        max_length=500,
        help_text='Provide a brief explanation for extending the bid validity period.'
    )


class TenderTypeForm(forms.Form):
    """
    Form for selecting tender type (for contract signature stages).
    """
    TENDER_CHOICES = [
        ('', '-- Select Tender Type --'),
        ('International', 'International Tender'),
        ('National', 'National Tender'),
    ]
    
    tender_type = forms.ChoiceField(
        label='Tender Type',
        choices=TENDER_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'tenderType',
            'required': True
        }),
        help_text='Select whether this is an International or National tender to determine contract signature timeline.'
    )
