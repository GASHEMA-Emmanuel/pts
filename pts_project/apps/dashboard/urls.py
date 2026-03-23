"""
URL patterns for dashboard app.
"""
from django.urls import path, re_path
from .views import (
    dashboard_view,
    admin_dashboard_view,
    admin_users_view,
    admin_divisions_view,
    admin_audit_logs_view,
    admin_system_settings_view,
    admin_reports_view,
    cbm_dashboard_view,
    cbm_calls_view,
    cbm_submissions_view,
    cbm_create_call_view,
    cbm_call_detail_view,
    cbm_publish_call_view,
    cbm_submission_detail_view,
    cbm_approve_submission_view,
    cbm_request_clarification_view,
    cbm_reject_submission_view,
    cbm_publish_submission_view,
    hod_dashboard_view,
    hod_submission_list_view,
    hod_submission_detail_view,
    hod_create_submission_view,
    hod_edit_submission_view,
    hod_submit_submission_view,
    hod_submit_clarification_view,
    hod_procurement_call_detail_view,
)
from .views_procurement import (
    procurement_dashboard_view,
    procurement_submission_detail_view,
    procurement_record_umucyo_view,
    procurement_update_status_view,
    procurement_record_award_view,
    procurement_add_comment_view,
    procurement_approve_draft_view,
    procurement_submit_compiled_document_view,
    procurement_return_draft_view,
    procurement_publish_plan_view,
    procurement_prepare_td_view,
    procurement_publish_td_view,
    procurement_notify_bidders_view,
    procurement_advance_stage_view,
)
from .views_procurement_additional import (
    procurement_submissions_list_view,
    procurement_compile_document_list_view,
    procurement_compile_all_view,
    procurement_publish_compiled_document_view,
    procurement_compiled_document_detail_view,
    cbm_compiled_documents_view,
    procurement_reports_view,
)
from .views_hod import (
    hod_reports_view,
)
from .views_tender import (
    submission_tender_list_view,
    tender_create_view,
    tender_create_standalone_view,
    tender_detail_view,
    tender_advance_view,
    tender_cbm_action_view,
    tenders_list_view,
)

urlpatterns = [
    path('', dashboard_view, name='dashboard'),
    
    # Admin routes
    path('admin/', admin_dashboard_view, name='admin_dashboard'),
    path('admin/users/', admin_users_view, name='admin_users'),
    path('admin/divisions/', admin_divisions_view, name='admin_divisions'),
    path('admin/audit-logs/', admin_audit_logs_view, name='admin_audit_logs'),
    path('admin/system-settings/', admin_system_settings_view, name='admin_system_settings'),
    path('admin/reports/', admin_reports_view, name='admin_reports'),
    
    # CBM routes
    path('cbm/', cbm_dashboard_view, name='cbm_dashboard'),
    path('cbm/calls/', cbm_calls_view, name='cbm_calls'),
    path('cbm/calls/create/', cbm_create_call_view, name='cbm_create_call'),
    path('cbm/calls/<uuid:call_id>/', cbm_call_detail_view, name='cbm_call_detail'),
    path('cbm/calls/<uuid:call_id>/publish/', cbm_publish_call_view, name='cbm_publish_call'),
    path('cbm/submissions/', cbm_submissions_view, name='cbm_submissions'),
    path('cbm/submissions/<uuid:submission_id>/', cbm_submission_detail_view, name='cbm_submission_detail'),
    path('cbm/submissions/<uuid:submission_id>/approve/', cbm_approve_submission_view, name='cbm_approve_submission'),
    path('cbm/submissions/<uuid:submission_id>/clarify/', cbm_request_clarification_view, name='cbm_request_clarification'),
    path('cbm/submissions/<uuid:submission_id>/reject/', cbm_reject_submission_view, name='cbm_reject_submission'),
    path('cbm/submissions/<uuid:submission_id>/publish/', cbm_publish_submission_view, name='cbm_publish_submission'),
    
    # HOD / Division Manager routes - specific routes first
    path('hod/calls/<uuid:call_id>/', hod_procurement_call_detail_view, name='hod_procurement_call_detail'),
    path('hod/submissions/<uuid:submission_id>/submit/', hod_submit_submission_view, name='hod_submit_submission'),
    path('hod/submissions/<uuid:submission_id>/edit/', hod_edit_submission_view, name='hod_edit_submission'),
    path('hod/submissions/<uuid:submission_id>/clarify/', hod_submit_clarification_view, name='hod_submit_clarification'),
    path('hod/submissions/<uuid:submission_id>/', hod_submission_detail_view, name='hod_submission_detail'),
    path('hod/submissions/create/', hod_create_submission_view, name='hod_create_submission'),
    path('hod/submissions/', hod_submission_list_view, name='hod_submissions'),
    path('hod/reports/', hod_reports_view, name='hod_reports'),
    path('hod/', hod_dashboard_view, name='hod_dashboard'),
    
    # Procurement Team routes
    path('procurement/', procurement_dashboard_view, name='procurement_dashboard'),
    path('procurement/submissions/', procurement_submissions_list_view, name='procurement_submissions'),
    path('procurement/compile-document/', procurement_compile_document_list_view, name='procurement_compile_document'),
    path('procurement/compile-document/submit/', procurement_compile_all_view, name='procurement_compile_all'),
    path('procurement/compile-document/<int:doc_id>/publish/', procurement_publish_compiled_document_view, name='procurement_publish_compiled_document'),
    path('procurement/compile-document/<int:doc_id>/', procurement_compiled_document_detail_view, name='procurement_compiled_document_detail'),
    path('procurement/reports/', procurement_reports_view, name='procurement_reports'),
    path('cbm/compiled-documents/', cbm_compiled_documents_view, name='cbm_compiled_documents'),
    path('procurement/submissions/<uuid:submission_id>/', procurement_submission_detail_view, name='procurement_submission_detail'),
    path('procurement/submissions/<uuid:submission_id>/approve-draft/', procurement_approve_draft_view, name='procurement_approve_draft'),
    path('procurement/submissions/<uuid:submission_id>/submit-compiled/', procurement_submit_compiled_document_view, name='procurement_submit_compiled_document'),
    path('procurement/submissions/<uuid:submission_id>/return-draft/', procurement_return_draft_view, name='procurement_return_draft'),
    path('procurement/submissions/<uuid:submission_id>/publish-plan/', procurement_publish_plan_view, name='procurement_publish_plan'),
    path('procurement/submissions/<uuid:submission_id>/prepare-td/', procurement_prepare_td_view, name='procurement_prepare_td'),
    path('procurement/submissions/<uuid:submission_id>/publish-td/', procurement_publish_td_view, name='procurement_publish_td'),
    path('procurement/submissions/<uuid:submission_id>/notify-bidders/', procurement_notify_bidders_view, name='procurement_notify_bidders'),
    path('procurement/submissions/<uuid:submission_id>/advance-stage/', procurement_advance_stage_view, name='procurement_advance_stage'),
    path('procurement/submissions/<uuid:submission_id>/umucyo/', procurement_record_umucyo_view, name='procurement_record_umucyo'),
    path('procurement/submissions/<uuid:submission_id>/status/', procurement_update_status_view, name='procurement_update_status'),
    path('procurement/submissions/<uuid:submission_id>/award/', procurement_record_award_view, name='procurement_record_award'),
    path('procurement/submissions/<uuid:submission_id>/comment/', procurement_add_comment_view, name='procurement_add_comment'),

    # Tender management routes (accessible by CBM + Procurement Team)
    path('tenders/', tenders_list_view, name='tenders_list'),
    path('tenders/create/', tender_create_standalone_view, name='tender_create_standalone'),
    path('submissions/<uuid:submission_id>/tenders/', submission_tender_list_view, name='submission_tender_list'),
    path('submissions/<uuid:submission_id>/tenders/create/', tender_create_view, name='tender_create'),
    re_path(r'^tenders/(?P<tender_number>.+)/advance/$', tender_advance_view, name='tender_advance'),
    re_path(r'^tenders/(?P<tender_number>.+)/cbm-action/$', tender_cbm_action_view, name='tender_cbm_action'),
    re_path(r'^tenders/(?P<tender_number>.+)/$', tender_detail_view, name='tender_detail'),
]
