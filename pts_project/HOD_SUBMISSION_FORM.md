# HOD Dashboard - Create Submission Form Implementation

## Changes Made

### 1. Created New Modal Component
**File**: `templates/procurement/create_submission_modal.html`

A comprehensive modal form for creating new submissions with the following features:
- **Procurement Call Selection**: Dropdown to select from active procurement calls
- **Auto-populate Deadline**: When a call is selected, the expected completion date is auto-populated from the call's end date
- **Submission Details**:
  - Title (required)
  - Description (optional)
  - Budget Amount in ZWL (required)
  - Priority Level (low/medium/high/critical)
  - Expected Completion Date (required)
  - Supporting Documents (file upload, multiple)
  - Special Requirements/Notes

### 2. Updated HOD Dashboard
**File**: `templates/dashboard/hod_dashboard.html`

- **Changed "Submit Now" button**: From plain link to Bootstrap button that triggers the modal
- **Button behavior**: `data-bs-toggle="modal" data-bs-target="#createSubmissionModal"`
- **Included modal**: Added `{% include 'procurement/create_submission_modal.html' %}` at the end of the template

### 3. Modal Functionality

**Form Submission**:
- Submits via POST to `/api/procurement/submissions/` REST API endpoint
- Automatically includes CSRF token
- Handles multipart form data for file uploads

**User Experience**:
- Shows loading spinner while creating
- Displays success/error alerts
- Redirects to HOD dashboard on success
- Allows dismissal and retry on error
- Auto-sets deadline from selected procurement call

**Form Validation**:
- Required fields: Procurement Call, Title, Budget Amount, Priority, Expected Completion Date
- File upload supports: PDF, Word, Excel, Images
- Budget input with ZWL currency prefix
- Form automatically disables submit button during processing

## User Workflow

1. **HOD views dashboard** and sees "Active Procurement Calls"
2. **For calls without submissions**, there's a "Submit Now" button
3. **Click "Submit Now"** → Modal opens with comprehensive form
4. **Select procurement call** → Deadline auto-fills from call's end date
5. **Fill in submission details** → Budget, priority, documents
6. **Click "Create Submission"** → Form submits to API
7. **On success** → Redirects to HOD dashboard
8. **New submission appears** in "Recent Submissions" section

## Form Fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| Procurement Call | Dropdown | Yes | Auto-populated from active calls |
| Title | Text | Yes | Submission title |
| Description | Textarea | No | Detailed description |
| Budget Amount | Currency | Yes | In ZWL |
| Priority | Dropdown | Yes | low/medium/high/critical |
| Expected Completion | Date | Yes | Auto-filled from call end date |
| Documents | File | No | Multiple file upload |
| Special Requirements | Textarea | No | Additional notes |

## Technical Implementation

**API Endpoint**: `/api/procurement/submissions/` (POST)

**Required Request Data**:
- `procurement_call`: UUID of selected call
- `title`: Submission title
- `description`: Description (optional)
- `budget_amount`: Decimal budget
- `priority`: Priority level
- `procurement_deadline`: ISO date format
- `documents`: File objects (optional)
- `special_requirements`: Notes (optional)

**Response**:
- Success: Returns submission object with `id` and `tracking_reference`
- Error: Returns validation errors

## Styling

- Modal uses Bootstrap 5 components
- Form fields with validation feedback
- Alert messages for success/error states
- Responsive layout that works on all screen sizes
- Color-coded priority badges

## Future Enhancements

1. **Field Validation**: Add real-time validation feedback
2. **Document Preview**: Show file previews before upload
3. **Draft Saving**: Auto-save form as draft
4. **Template Selection**: Pre-fill common procurement types
5. **Bulk Submissions**: Add multiple items in one submission
6. **Document Templates**: Provide downloadable submission templates

---

**Status**: ✅ Complete and Ready for Testing
**Date**: February 5, 2026
