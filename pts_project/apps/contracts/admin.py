from django.contrib import admin
from .models import (
    Contract, PurchaseOrder, ContractHistory,
    PerformanceGuarantee, POPerformanceGuarantee, ContractCommunication,
)


class PurchaseOrderInline(admin.TabularInline):
    model = PurchaseOrder
    extra = 0
    fields = ('po_number', 'description', 'issued_date', 'delivery_date', 'status',
              'received_date', 'evaluation_date', 'completion_certificate_date')


class ContractHistoryInline(admin.TabularInline):
    model = ContractHistory
    extra = 0
    fields = ('action', 'notes', 'action_by', 'created_at')
    readonly_fields = ('created_at',)


class PerformanceGuaranteeInline(admin.TabularInline):
    model = PerformanceGuarantee
    extra = 0
    fields = ('file', 'expiry_date', 'description', 'uploaded_by', 'uploaded_at')
    readonly_fields = ('uploaded_at',)


class ContractCommunicationInline(admin.TabularInline):
    model = ContractCommunication
    extra = 0
    fields = ('subject', 'message', 'attachment', 'sent_by', 'created_at')
    readonly_fields = ('created_at',)


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ('contract_number', 'contract_name', 'contract_type', 'division', 'status',
                    'received_date', 'evaluation_date', 'created_by', 'created_at')
    list_filter  = ('contract_type', 'status')
    search_fields = ('contract_number', 'contract_name')
    inlines = [PurchaseOrderInline, PerformanceGuaranteeInline, ContractCommunicationInline, ContractHistoryInline]


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ('po_number', 'contract', 'issued_date', 'delivery_date', 'status',
                    'received_date', 'evaluation_date')
    list_filter  = ('status',)
    search_fields = ('po_number', 'contract__contract_number')


@admin.register(PerformanceGuarantee)
class PerformanceGuaranteeAdmin(admin.ModelAdmin):
    list_display = ('contract', 'expiry_date', 'description', 'uploaded_by', 'uploaded_at')
    list_filter  = ('expiry_date',)
    search_fields = ('contract__contract_number',)


@admin.register(POPerformanceGuarantee)
class POPerformanceGuaranteeAdmin(admin.ModelAdmin):
    list_display = ('purchase_order', 'expiry_date', 'description', 'uploaded_by', 'uploaded_at')
    list_filter  = ('expiry_date',)
    search_fields = ('purchase_order__po_number',)


@admin.register(ContractCommunication)
class ContractCommunicationAdmin(admin.ModelAdmin):
    list_display = ('contract', 'subject', 'sent_by', 'created_at')
    list_filter  = ('created_at',)
    search_fields = ('contract__contract_number', 'subject', 'message')
