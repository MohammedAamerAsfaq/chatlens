# 📋 Backend Development Guide - Django with Function Views

This comprehensive guide explains how to work with the unique Vue.js + Django hybrid architecture used in Cellusense ERP.

## 📋 Table of Contents

- [🏗️ Architecture Overview](#️-architecture-overview)
- [📁 Project Structure](#-project-structure)
- [🧱 Core Patterns & Best Practices](#-core-patterns--best-practices)
- [🌐 URL Design Patterns](#-url-design-patterns)
- [🔧 Function-Based View Implementation](#-function-based-view-implementation)
- [📚 Repository Pattern Deep Dive](#-repository-pattern-deep-dive)
- [✅ Form Validation & Error Handling](#-form-validation--error-handling)
- [🔄 Transaction Management](#-transaction-management)
- [📝 Logging & Audit Trails](#-logging--audit-trails)
- [📖 Complete Examples](#-complete-examples)
- [🚨 Troubleshooting](#-troubleshooting)
- [⚡ Performance Optimization](#-performance-optimization)

---

## 🏗️ Architecture Overview

### 🔀 Hybrid Approach
- **Backend**: Django handles routing, authentication, data processing, and initial page rendering
- **Frontend**: Vue.js (Options API) provides interactivity within Django templates
- **Integration**: Vue components are embedded directly in Django templates, no separate SPA

### 🔑 Key Characteristics of the Project
* Utilizes **function-based views (FBVs)** for handling HTTP requests and responses.
* Implements the **repository pattern** to cleanly extract and manage model data from incoming requests.
* Leverages **Django forms** for structured data validation and sanitization.
* Employs **exception handling** to display meaningful error messages directly on the UI.
* Wraps critical operations with **`transaction.atomic`** to ensure full commit or complete rollback, maintaining data integrity.
* Integrates **logging mechanisms** to track all transactional activities such as add, update, and delete operations.

---

## 📁 Project Structure

```
cellusense2/
├── cashier/
    ├── __init__.py                          # Package initializer
    ├── admin.py                             # Register models for Django admin interface
    ├── urls.py                              # URL configuration for this app
    ├── migrations/                          # Django migrations directory
    │   └── __init__.py
    ├── models/                              # All model definitions
    │   ├── __init__.py                      # Import all models here for Django to detect during migration
    │   ├── header.py                        # For Cashier Header Model
    │   ├── itemline.py                      # For Cashier Item Line Model
    │   ├── account_user_permissions.py      # For Account User Permissions Model
    ├── forms/                               # Django forms for models
    │   ├── cashier_header_form.py           # Cashier Header Form
    │   ├── cashier_itemline_form.py         # Cashier Item Line Form
    ├── repository/                          # Business logic and data access layer
    │   ├── cashier_header_repo.py           # Cashier Header Repository
    │   ├── cashier_itemline_repo.py         # Cashier Item Line Repository
    ├── function_views/                      # Views using function-based approach
    │   ├── cashier.py                       # Cashier Views
    ├── templates/                           # HTML templates
    │   ├── cashier/
    │   │   ├── cashier.html                 # Main page
    │   ├── cashier_debug_data.html          # Debug UI for inspecting values
    │   ├── cashier_navigation_panel.html    # Cashier Navigation Panel
    ├── templatetags/                        # Custom Django template filters or tags
    │   ├── cashier_template.py
```

---

## 🧱 Core Patterns & Best Practices

### Function-Based Views vs Class-Based Views

**Why FBVs in Cellusense?**
- **Simplicity**: Easier to understand and debug for complex business logic
- **Flexibility**: No inheritance constraints, custom logic flows
- **Performance**: Slightly better performance for simple operations
- **Debugging**: Clearer stack traces and easier testing

**When to use FBVs:**
- Complex business logic with multiple steps
- Custom error handling and validation
- Integration with external services
- When you need full control over the request/response cycle

### Repository Pattern Benefits

**Separation of Concerns:**
- Business logic separated from HTTP handling
- Easier testing of business rules
- Reusable across different view types
- Cleaner code organization

**Repository Responsibilities:**
- Data extraction from requests
- Business rule validation
- Database operations
- Error handling and logging

---

## 🌐 URL Design Patterns

### Standard URL Structure

```python
# urls.py
from django.urls import path
from . import views

app_name = 'cashier'

urlpatterns = [
    # Index/List View
    path("index/", views.index, name="index"),
    path("cashier/", views.index, name="index"),  # Alternate path

    # Grid/List View (AJAX)
    path("grid_view/", views.grid_view, name="grid-view"),

    # Add/Update Operations
    path("operation/<str:opp>/<int:pk>", views.operation_add_update, name="operation-add-update"),
    path("save/<int:pk>/<str:opp>", views.save, name="save"),

    # Record Navigation
    path("get_previous_cs_id/<int:id>", views.get_previous_cs_id, name="get-previous-cs-id"),
    path("get_next_cs_id/<int:id>", views.get_next_cs_id, name="get-next-cs-id"),

    # Delete Operation
    path("delete/<int:pk>", views.delete, name="delete-cashier"),
]
```

### URL Naming Conventions

- **index**: Main page or list view
- **grid_view**: AJAX endpoint for DataTables
- **operation/{opp}/{pk}**: Add/update forms (opp = 'add' or 'update')
- **save/{pk}/{opp}**: Save endpoint for forms
- **get_previous/next_{id}**: Record navigation
- **delete/{pk}**: Delete operations

---

## 🔧 Function-Based View Implementation

### Index Page View

```python
def index(request):
    """
    Main page view that renders the initial template.
    No complex logic - just template rendering.
    """
    return render(request, "cashier/cashier.html")
```

### Grid View (DataTables AJAX)

```python
def grid_view(request):
    """
    Server-side processing for DataTables.
    Handles filtering, sorting, and pagination.
    """
    start = request.GET.get("start")
    length = request.GET.get("length")

    # Calculate page number
    try:
        page_number = (int(start) // int(length)) + 1
    except ZeroDivisionError:
        page_number = 1

    # Build query with filters
    query = Q()

    # Add search filters
    common_search_string = request.GET.get("search[value]")
    if common_search_string:
        query &= Q(id=common_search_string) | Q(total_cash_count=common_search_string)

    # Column-specific filters
    for i in range(1, 5):
        column_search = request.GET.get(f"columns[{i}][search][value]")
        if column_search:
            column_name = request.GET.get(f"columns[{i}][data]")
            if column_name == "id":
                query &= Q(id=column_search)

    # Apply filters and get data
    if common_search_string:
        data = CashierHeader.objects.filter(query).values(
            "id", "total_cash_count", "transaction_date", "memo", "work_id"
        )
    else:
        data = CashierHeader.objects.all().values(
            "id", "total_cash_count", "transaction_date", "memo", "work_id"
        )

    # Sorting
    sort_field = request.GET.get("order[0][column]")
    sort_direction = request.GET.get("order[0][dir]")
    sort_field_name = request.GET.get(f"columns[{sort_field}][data]")

    if sort_field_name:
        if sort_direction == "asc":
            data = sorted(data, key=lambda x: x[sort_field_name])
        else:
            data = sorted(data, key=lambda x: x[sort_field_name], reverse=True)

    # Pagination
    paginator = Paginator(data, length)
    try:
        page = paginator.get_page(page_number)
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)

    # Return JSON response
    messages_dict = get_messages_from_session(request)
    response = {
        "draw": request.GET.get("draw"),
        "recordsTotal": paginator.count,
        "recordsFiltered": paginator.count,
        "data": list(page.object_list),
        "messages": messages_dict,
    }

    return JsonResponse(response, safe=False)
```

### Add/Update Operation View

```python
def operation_add_update(request, pk, opp="add"):
    """
    Renders the form for add/update operations.
    Prepares context with necessary data.
    """
    try:
        # Generate save URL
        save_url = reverse(
            "cashier:save",
            kwargs={"pk": pk, "opp": opp},
        )

        # Initialize or get existing object
        cs_object = CashierHeader()
        next_estimated_id = pk

        if opp == "add":
            next_estimated_id = cs_object.getNextEstimatedId()

        context = {
            "cs_header_id": next_estimated_id,
            "opp": opp,
            "save_url": save_url,
        }

        return render(request, "cashier/cashier.html", context)

    except Exception as e:
        messages.error(request, e)
        return render(request, "dashboard/error.html", {"error": e})
```

### Save Operation View

```python
def save(request, pk, opp="add"):
    """
    Handles form submission for both add and update operations.
    Uses repository pattern for business logic.
    """
    try:
        with transaction.atomic():
            # Get content types for logging
            content_type_cashier_header = ContentType.objects.get_for_model(CashierHeader)
            content_type_cashier_line = ContentType.objects.get_for_model(CashierLine)

            # Create or get work object
            work = Work()
            if opp == "add":
                work.content_type = content_type_cashier_header
                work.save()
            else:
                work = CashierHeader.objects.get(id=pk).work

            # Process header using repository
            cashier_header_repo = CashierHeaderRepo()
            cs_header_form = cashier_header_repo.extract_cahierheader_object_from_request(
                request, work.id
            )

            # Get or create header instance
            cs_header = CashierHeader() if opp == "add" else CashierHeader.objects.get(id=pk)
            cs_header_form.instance = cs_header

            # Validate and save
            if not cs_header_form.is_valid():
                messages.error(request, cs_header_form.errors)
                raise Exception(cs_header_form.errors)

            cs_header_form.save()

            # Log the transaction
            log_message = (
                f"{Messages.CASHIER_UPDATED.value} for Cashier"
                if opp == "update"
                else f"{Messages.CASHIER_ADDED.value} for Cashier"
            )
            log_info(request, log_message, work.id, cs_header.id, content_type_cashier_header)

            # Process line items
            cashier_line_repo = CashierItemLineRepo()
            cs_line_forms = cashier_line_repo.extract_cashierline_object_from_request(
                request, cs_header, work.id
            )

            # Save each line item
            for cs_line_form in cs_line_forms:
                cs_line_object = CashierLine()
                if cs_line_form.data["csitemlineid"] != 0:
                    cs_line_object = CashierLine.objects.get(id=cs_line_form.data["csitemlineid"])
                    cs_line_form.instance = cs_line_object

                if not cs_line_form.is_valid():
                    messages.error(request, cs_line_form.errors)
                    raise Exception(cs_line_form.errors)

                cs_line_form.save()

            # Handle deleted items
            cs_line_data_deleted_lines = request.POST.get("cs_line_data_deleted_data")
            cs_line_data_deleted_lines = json.loads(cs_line_data_deleted_lines) if cs_line_data_deleted_lines else []

            for item in cs_line_data_deleted_lines:
                if item["itemLineId"]:
                    line_to_delete = CashierLine.objects.get(id=item["itemLineId"])
                    # Archive before delete
                    archive_deleted_record = DeletedRecords.objects.create(
                        user=request.user,
                        work_id=work.id,
                        content_type=content_type_cashier_line,
                        object_id=line_to_delete.id,
                        json_object=serializers.serialize("json", [line_to_delete]),
                    )
                    archive_deleted_record.save()
                    line_to_delete.delete()

            # Log line operations
            log_message = (
                f"{Messages.CASHIER_LINE_UPDATED.value} for Cashier"
                if opp == "update"
                else f"{Messages.CASHIER_LINE_ADDED.value} for Cashier"
            )
            log_info(request, log_message, work.id, cs_header.id, content_type_cashier_line)

            # Return success response
            json_data = get_json_object_for_logger(
                log_message, 0, content_type_cashier_header, cs_header.id, request
            )

            return JsonResponse({"success": True, "json_data": json_data}, safe=False)

    except Exception as e:
        errorMessages = e.args[0]
        return JsonResponse(
            {"success": False, "errorMessages": errorMessages},
            safe=False,
            status=400
        )
```

---

## 📚 Repository Pattern Deep Dive

### Repository Structure

```python
class CashierHeaderRepo:
    """
    Repository for Cashier Header business logic.
    Handles data extraction, validation, and persistence.
    """

    def extract_cahierheader_object_from_request(self, request, work_id, **kwargs):
        """
        Extract and validate cashier header data from request.
        Returns a bound form ready for saving.
        """
        cs_header_data = request.POST.get("cs_header_data")
        cs_header_data = json.loads(cs_header_data)

        work_object = Work.objects.get(id=work_id)

        if not cs_header_data:
            messages.error(request, "Invalid cashier header data.")
            raise Exception("Invalid cashier header data.")

        # Extract form data
        cash_account_selected = cs_header_data[0]["cash_account_selected"]
        memo = cs_header_data[0]["memo"]
        transaction_date = cs_header_data[0]["date"]
        cash_account_balance = cs_header_data[0]["cash_account_balance"]
        total_cash_count = cs_header_data[0]["total_cash_count"]

        # Business validations
        if not cash_account_selected or cash_account_selected == 0:
            raise Exception("Cashier Account is required.")

        if not total_cash_count:
            raise Exception("Total Cash Count is required.")

        # Get related objects
        account = ChartofAccounts.objects.get(id=cash_account_selected)

        # Type casting utility
        type_cast = Type_Cast()

        # Create form with validated data
        cs_header_form = CashierHeaderForm({
            "work": work_object,
            "cash_account": account,
            "cash_account_selected": cash_account_selected,
            "memo": memo,
            "date": transaction_date,
            "transaction_date": transaction_date,
            "cash_account_balance": type_cast.convert_to_float(cash_account_balance),
            "total_cash_count": type_cast.convert_to_float(total_cash_count),
            "user": request.user,
        })

        return cs_header_form
```

### Repository Best Practices

**Single Responsibility:**
- Each repository handles one model/domain
- Clear separation between data access and business logic
- Consistent error handling patterns

**Data Validation:**
- Validate business rules in repository methods
- Use Django forms for field-level validation
- Custom validation for complex business rules

**Error Handling:**
- Raise specific exceptions with meaningful messages
- Log errors for debugging
- Return structured error responses

---

## ✅ Form Validation & Error Handling

### Django Form Structure

```python
# forms/cashier_header_form.py
from django import forms
from .models import CashierHeader

class CashierHeaderForm(forms.ModelForm):
    """
    Form for Cashier Header with custom validation.
    """

    class Meta:
        model = CashierHeader
        fields = [
            'work', 'cash_account', 'memo', 'transaction_date',
            'cash_account_balance', 'total_cash_count', 'user'
        ]

    def clean_total_cash_count(self):
        """
        Custom validation for total cash count.
        """
        total_cash = self.cleaned_data.get('total_cash_count')

        if total_cash <= 0:
            raise forms.ValidationError("Total cash count must be positive.")

        if total_cash > 1000000:  # Business rule
            raise forms.ValidationError("Total cash count cannot exceed 1,000,000.")

        return total_cash

    def clean(self):
        """
        Cross-field validation.
        """
        cleaned_data = super().clean()
        cash_account_balance = cleaned_data.get('cash_account_balance')
        total_cash_count = cleaned_data.get('total_cash_count')

        # Business rule: cash count should not exceed account balance
        if cash_account_balance and total_cash_count:
            if total_cash_count > cash_account_balance:
                raise forms.ValidationError(
                    "Total cash count cannot exceed account balance."
                )

        return cleaned_data
```

### Error Handling Patterns

```python
# In views.py
def save_view(request, pk, opp="add"):
    try:
        # Business logic here
        pass

    except ValidationError as e:
        # Form validation errors
        messages.error(request, e.messages)
        return JsonResponse({
            "success": False,
            "errors": e.messages
        }, status=400)

    except IntegrityError as e:
        # Database constraint violations
        logger.error(f"Database integrity error: {e}")
        messages.error(request, "Data integrity violation. Please check your input.")
        return JsonResponse({
            "success": False,
            "error": "Database constraint violation"
        }, status=400)

    except Exception as e:
        # Generic error handling
        logger.exception(f"Unexpected error in save_view: {e}")
        messages.error(request, "An unexpected error occurred. Please try again.")
        return JsonResponse({
            "success": False,
            "error": "Internal server error"
        }, status=500)
```

---

## 🔄 Transaction Management

### Atomic Transactions

```python
from django.db import transaction

def save_view(request, pk, opp="add"):
    """
    All database operations wrapped in a single transaction.
    Either all succeed or all rollback.
    """
    try:
        with transaction.atomic():
            # Create work object
            work = Work()
            work.content_type = ContentType.objects.get_for_model(CashierHeader)
            work.save()

            # Process header
            header_repo = CashierHeaderRepo()
            header_form = header_repo.extract_cahierheader_object_from_request(request, work.id)

            # Save header
            header = CashierHeader()
            header_form.instance = header

            if not header_form.is_valid():
                raise ValidationError(header_form.errors)

            header_form.save()

            # Process line items
            line_repo = CashierItemLineRepo()
            line_forms = line_repo.extract_cashierline_object_from_request(request, header, work.id)

            for line_form in line_forms:
                # Save each line item
                line = CashierLine()
                line_form.instance = line

                if not line_form.is_valid():
                    raise ValidationError(line_form.errors)

                line_form.save()

            # Log success
            log_info(request, "Cashier transaction completed", work.id, header.id)

            return JsonResponse({"success": True})

    except Exception as e:
        # Transaction automatically rolls back on exception
        logger.error(f"Transaction failed: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=400)
```

### Transaction Best Practices

**When to use transactions:**
- Multiple related database operations
- Financial transactions (debits/credits)
- Master-detail relationships
- Any operation where consistency is critical

**Transaction Scope:**
- Keep transactions as short as possible
- Avoid user interaction within transactions
- Use `select_for_update()` for concurrent access
- Handle deadlocks gracefully

---

## 📝 Logging & Audit Trails

### Logging Configuration

```python
# settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'logs/cellusense.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
```

### Audit Logging Implementation

```python
# utils/logging_utils.py
def log_info(request, message, work_id, object_id, content_type):
    """
    Log business operations for audit trails.
    """
    logger.info(
        f"User: {request.user.username} | "
        f"Work ID: {work_id} | "
        f"Object ID: {object_id} | "
        f"Content Type: {content_type} | "
        f"Message: {message} | "
        f"IP: {get_client_ip(request)}"
    )

def get_json_object_for_logger(message, line_id, content_type, header_id, request):
    """
    Create structured log data for frontend.
    """
    return {
        "message": message,
        "line_id": line_id,
        "content_type_id": content_type.id,
        "header_id": header_id,
        "user": request.user.username,
        "timestamp": timezone.now().isoformat(),
    }
```

### Audit Trail Models

```python
# models/audit.py
class AuditLog(models.Model):
    """
    Comprehensive audit trail for all business operations.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=100)
    model_name = models.CharField(max_length=100)
    object_id = models.PositiveIntegerField()
    old_values = models.JSONField(null=True, blank=True)
    new_values = models.JSONField(null=True, blank=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['model_name', 'object_id']),
        ]
```

---

## 📖 Complete Examples

### Cashier Line Repository

```python
class CashierItemLineRepo:
    """
    Repository for Cashier Line Items.
    Handles complex business logic for line item processing.
    """

    def extract_cashierline_object_from_request(self, request, cs_header_object, work_id, **kwargs):
        """
        Extract and validate line items from request.
        Handles complex currency calculations and validations.
        """
        try:
            cs_line_data = request.POST.get("cs_line_data")
            cs_line_data = json.loads(cs_line_data)
            work_object = Work.objects.get(id=work_id)

            if not cs_line_data:
                messages.error(request, "Invalid cashier item line data.")
                raise Exception("Invalid cashier item line data.")

            cs_line_forms = []
            type_cast = Type_Cast()

            for item in cs_line_data:
                # Skip empty rows
                if item["row_empty"] == True:
                    continue

                # Extract form data
                csitemlineid = item.get("itemLineId", 0)
                thousand = type_cast.convert_to_decimal(item["thousand"])
                fivehundered = type_cast.convert_to_decimal(item["fivehundered"])
                twohundred = type_cast.convert_to_decimal(item["twohundred"])
                hundred = type_cast.convert_to_decimal(item["hundred"])
                fifty = type_cast.convert_to_decimal(item["fifty"])
                twenty = type_cast.convert_to_decimal(item["twenty"])
                ten = type_cast.convert_to_decimal(item["ten"])
                five = type_cast.convert_to_decimal(item["five"])
                coin = type_cast.convert_to_decimal(item["coin"])
                line_total = type_cast.convert_to_decimal(item["line_total"])
                memo = item["memo"]

                # Business validation: line total should match sum
                calculated_total = (
                    thousand * 1000 + fivehundered * 500 + twohundred * 200 +
                    hundred * 100 + fifty * 50 + twenty * 20 + ten * 10 +
                    five * 5 + coin * 1
                )

                if calculated_total != line_total:
                    raise Exception(f"Line total mismatch for item. Expected: {calculated_total}, Got: {line_total}")

                # Create form
                cs_line_form = CashierItemLineForm({
                    "csitemlineid": csitemlineid,
                    "work": work_object,
                    "header": cs_header_object,
                    "thousand": thousand,
                    "five_hundred": fivehundered,
                    "two_hundred": twohundred,
                    "one_hundred": hundred,
                    "fifty": fifty,
                    "twenty": twenty,
                    "ten": ten,
                    "five": five,
                    "one": coin,
                    "line_total": line_total,
                    "memo": memo,
                })

                cs_line_forms.append(cs_line_form)

            return cs_line_forms

        except Exception as e:
            errorMessages = e.args[0]
            raise Exception(errorMessages)
```

### Navigation Views

```python
def get_previous_cs_id(request, id):
    """
    Navigate to previous record.
    Returns JSON with previous record ID.
    """
    try:
        current_record = CashierHeader.objects.get(id=id)
        previous_record = CashierHeader.objects.filter(
            id__lt=current_record.id
        ).order_by('-id').first()

        if previous_record:
            return JsonResponse({
                "success": True,
                "previous_id": previous_record.id
            })
        else:
            return JsonResponse({
                "success": False,
                "message": "No previous record found"
            })

    except CashierHeader.DoesNotExist:
        return JsonResponse({
            "success": False,
            "message": "Record not found"
        }, status=404)
    except Exception as e:
        logger.error(f"Error in get_previous_cs_id: {e}")
        return JsonResponse({
            "success": False,
            "message": "Internal server error"
        }, status=500)

def get_next_cs_id(request, id):
    """
    Navigate to next record.
    Similar logic to previous navigation.
    """
    try:
        current_record = CashierHeader.objects.get(id=id)
        next_record = CashierHeader.objects.filter(
            id__gt=current_record.id
        ).order_by('id').first()

        if next_record:
            return JsonResponse({
                "success": True,
                "next_id": next_record.id
            })
        else:
            return JsonResponse({
                "success": False,
                "message": "No next record found"
            })

    except CashierHeader.DoesNotExist:
        return JsonResponse({
            "success": False,
            "message": "Record not found"
        }, status=404)
    except Exception as e:
        logger.error(f"Error in get_next_cs_id: {e}")
        return JsonResponse({
            "success": False,
            "message": "Internal server error"
        }, status=500)
```

---

## 🚨 Troubleshooting

### Common Issues & Solutions

#### Repository Errors
```python
# Issue: "Invalid JSON data"
# Solution: Check request.POST structure
cs_header_data = request.POST.get("cs_header_data")
if not cs_header_data:
    raise Exception("Missing header data in request")

try:
    data = json.loads(cs_header_data)
except json.JSONDecodeError:
    raise Exception("Invalid JSON format in header data")
```

#### Transaction Failures
```python
# Issue: "Transaction rolled back"
# Solution: Check for validation errors before transaction
if not form.is_valid():
    # Handle validation errors outside transaction
    messages.error(request, form.errors)
    raise ValidationError(form.errors)

with transaction.atomic():
    # Safe to save inside transaction
    form.save()
```

#### Performance Issues
```python
# Issue: Slow queries in grid_view
# Solution: Add database indexes
# In models.py
class Meta:
    indexes = [
        models.Index(fields=['transaction_date']),
        models.Index(fields=['cash_account']),
    ]
```

#### Memory Issues
```python
# Issue: Large querysets causing memory errors
# Solution: Use iterator() for large datasets
def grid_view(request):
    # Instead of .values() which loads all into memory
    data = CashierHeader.objects.all().iterator()

    # Process in chunks
    results = []
    for item in data:
        results.append({
            'id': item.id,
            'total': item.total_cash_count,
        })
        if len(results) >= 100:  # Process in batches
            break
```

---

## ⚡ Performance Optimization

### Database Optimization

**Indexes:**
```python
# Add to model Meta class
class CashierHeader(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=['transaction_date', 'cash_account']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['work']),
        ]
```

**Query Optimization:**
```python
# Use select_related for foreign keys
def get_cashier_with_account(cashier_id):
    return CashierHeader.objects.select_related('cash_account', 'work').get(id=cashier_id)

# Use prefetch_related for reverse foreign keys
def get_cashier_with_lines(cashier_id):
    return CashierHeader.objects.prefetch_related('cashier_lines').get(id=cashier_id)
```

### Caching Strategies

```python
from django.core.cache import cache

def get_account_balance(account_id):
    """
    Cache account balance to reduce database queries.
    """
    cache_key = f"account_balance_{account_id}"
    balance = cache.get(cache_key)

    if balance is None:
        account = ChartofAccounts.objects.get(id=account_id)
        balance = account.current_balance
        cache.set(cache_key, balance, timeout=300)  # 5 minutes

    return balance
```

### View Optimization

**Pagination Best Practices:**
```python
def optimized_grid_view(request):
    """
    Optimized DataTables view with proper pagination.
    """
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 10))

    # Use QuerySet directly instead of values() then sorting
    queryset = CashierHeader.objects.all()

    # Apply filters at database level
    search_value = request.GET.get('search[value]')
    if search_value:
        queryset = queryset.filter(
            Q(id__icontains=search_value) |
            Q(total_cash_count__icontains=search_value)
        )

    # Get total count before pagination
    total_count = queryset.count()

    # Apply sorting
    order_column = request.GET.get('order[0][column]')
    order_dir = request.GET.get('order[0][dir]')

    if order_column:
        column_name = request.GET.get(f'columns[{order_column}][data]')
        if order_dir == 'desc':
            queryset = queryset.order_by(f'-{column_name}')
        else:
            queryset = queryset.order_by(column_name)

    # Apply pagination
    queryset = queryset[start:start + length]

    # Serialize data
    data = list(queryset.values(
        'id', 'total_cash_count', 'transaction_date', 'memo'
    ))

    return JsonResponse({
        'draw': request.GET.get('draw'),
        'recordsTotal': total_count,
        'recordsFiltered': total_count,
        'data': data
    })
```

---

*Last updated: January 2026* | *Version: 2.0.0*
### 🧱 Function-based View Page
#### Index Page or Grid View Page
```python
def index(request):
    return render(request, "cashier/cashier.html")
```
#### Grid View code return on ajax request from server
```python
def grid_view(request):
    """Grid View for Sales Return"""

    start = request.GET.get("start")
    length = request.GET.get("length")

    # Calculate the page number based on the start and length parameters
    try:
        page_number = (int(start) // int(length)) + 1
    except ZeroDivisionError:
        page_number = 1

    # Retrieve the data for the current page
    try: 

        # check search string from request
        common_search_string = request.GET.get("search[value]")

        query = Q()        

        query &= Q(cash_account_id=request.GET.get("cash_account_id"))

        for i in range(1, 5):
            column_search = request.GET.get(f"columns[{i}][search][value]")
            if column_search:
                # get the column name
                column_name = request.GET.get(f"columns[{i}][data]")
                # print(f"column_name is {column_name}")
                if column_name == "id":
                    query &= Q(id=column_search)
                elif column_name == "transaction_date":
                    query &= Q(transaction_date__icontains=column_search)       
        

        if common_search_string:
            # search this string in all searchable fields
            data = CashierHeader.objects.filter(
                Q(id=common_search_string)
                | Q(total_cash_count=common_search_string)
            ).values(
                "id",
                "total_cash_count",
                "transaction_date",
                "memo",
                "work_id",
            )
        elif query:
            data = CashierHeader.objects.filter(query).values(
                "id",
                "total_cash_count",
                "transaction_date",
                "memo",
                "work_id",
            )
        else:
            data = CashierHeader.objects.all().values(
                "id",
                "total_cash_count",
                "transaction_date",
                "memo",
                "work_id",
            )

        # get the field clicked to sort
        sort_field = request.GET.get("order[0][column]")
        # get the direction of the sort
        sort_direction = request.GET.get("order[0][dir]")
        # get the field name
        sort_field_name = request.GET.get(f"columns[{sort_field}][data]")

        if sort_field_name != "":
            if sort_direction == "asc":
                data = sorted(data, key=lambda x: x[sort_field_name])
            else:
                data = sorted(data, key=lambda x: x[sort_field_name], reverse=True)

        if length == "-1":
            # return all records
            length = data.count()

        paginator = Paginator(data, length)

        page = paginator.get_page(page_number)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        page = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        page = paginator.page(paginator.num_pages)
    except Exception as e:
        print(f"Exception is {e}")
        # messages.error(request, f"Exception is {e}")
        return JsonResponse("Exception is {e}")

    messages_dict = get_messages_from_session(request)

    # Build the JSON response
    response = {
        "draw": request.GET.get("draw"),
        "recordsTotal": paginator.count,
        "recordsFiltered": paginator.count,
        "data": list(page.object_list),
        "messages": messages_dict,
    }

    return JsonResponse(response, safe=False)
```
### Initial loader for Add / Update request
```python
def operation_add_update(request, pk, opp="add"):
    try:
        save_url = reverse(
            "cashier:save",
            kwargs={"pk": pk, "opp": opp},
        )
        
        cs_object = CashierHeader()

        next_estimated_id = pk

        if opp == "add":
            next_estimated_id = cs_object.getNextEstimatedId()

        context = {
            "cs_header_id": next_estimated_id,
            "opp": opp,
            "save_url": save_url,
        }
        return render(request, "cashier/cashier.html", context)

    except Exception as e:
        messages.error(request, e)
        print(f"Exception is {e}")
        # return to error page with exception
        return render(request, "dashboard/error.html", {"error": e})
```
### Save Operation for Add / Update request
### Its important to note that every transaction needs to be assigned to a work using work_id
```python
def save(request, pk, opp="add"):
    try:
        with transaction.atomic():
            content_type_cashier_header = ContentType.objects.get_for_model(
                CashierHeader
            )
            content_type_cashier_line = ContentType.objects.get_for_model(CashierLine)

            work = Work()
            if opp == "add":
                work.content_type = content_type_cashier_header
                work.save()
            else:
                work = CashierHeader.objects.get(id=pk).work

            # Save work header
            cashier_header_repo = CashierHeaderRepo()
            cs_header_form = (
                cashier_header_repo.extract_cahierheader_object_from_request(
                    request, work.id
                )
            )

            cs_header = (
                CashierHeader.objects.get(id=pk) if opp == "update" else CashierHeader()
            )

            cs_header_form.instance = cs_header
            if not cs_header_form.is_valid():
                messages.error(request, cs_header_form.errors)
                raise Exception(cs_header_form.errors)

            cs_header_form.save()

            # Create log message for this transaction
            log_message = (
                f"{Messages.CASHIER_UPDATED.value} for Cashier"
                if opp == "update"
                else f"{Messages.CASHIER_ADDED.value} for Cashier"
            )

            log_info(
                request, log_message, work.id, cs_header.id, content_type_cashier_header
            )

            cashier_line_repo = CashierItemLineRepo()
            cs_line_forms = cashier_line_repo.extract_cashierline_object_from_request(
                request, cs_header, work.id
            )

            for cs_line_form in cs_line_forms:
                cs_line_object = CashierLine()

                if cs_line_form.data["csitemlineid"] != 0:
                    cs_line_object = CashierLine.objects.get(
                        id=cs_line_form.data["csitemlineid"]
                    )
                    cs_line_form.instance = cs_line_object

                if not cs_line_form.is_valid():
                    messages.error(request, cs_line_form.errors)
                    raise Exception(cs_line_form.errors)

                cs_line_form.save()

            # convert csItemLines marked for deletion to json object
            cs_line_data_deleted_lines = request.POST.get("cs_line_data_deleted_data")

            # convert srItemLines marked for deletion to json object
            cs_line_data_deleted_lines = (
                json.loads(cs_line_data_deleted_lines)
                if cs_line_data_deleted_lines
                else []
            )

            for item in cs_line_data_deleted_lines:
                if not item["itemLineId"]:
                    continue
                line_to_delete = CashierLine.objects.get(id=item["itemLineId"])
                archive_deleted_record = DeletedRecords.objects.create(
                    user=request.user,
                    work_id=work.id,
                    content_type=content_type_cashier_line,
                    object_id=line_to_delete.id,
                    json_object=serializers.serialize("json", [line_to_delete]),
                )
                archive_deleted_record.save()
                line_to_delete.delete()

            # Create log message for this transaction
            log_message = (
                f"{Messages.CASHIER_LINE_UPDATED.value} for Cashier"
                if opp == "update"
                else f"{Messages.CASHIER_LINE_ADDED.value} for Cashier"
            )

            log_info(
                request, log_message, work.id, cs_header.id, content_type_cashier_line
            )

            json_data = get_json_object_for_logger(
                log_message,
                0,
                content_type_cashier_header,
                cs_header.id,
                request,
            )

            return JsonResponse({"success": True, "json_data": json_data}, safe=False)

    except Exception as e:
        print(f"Exception is {e}")
        errorMessages = e.args[0]
        return JsonResponse(
            {"success": True, "errorMessages": errorMessages}, safe=False, status=400
        )
```
### Extracting Cashier Header Object from Request
#### Using repository pattern
```python
class CashierHeaderRepo:

    def extract_cahierheader_object_from_request(self, request, work_id, **kwargs):
        """Extract cashier header object from request"""

        cs_header_data = request.POST.get("cs_header_data")
        cs_header_data = json.loads(cs_header_data)

        work_object = Work.objects.get(id=work_id)

        if not cs_header_data:
            messages.error(request, "Invalid cashier header data.")
            raise Exception("Invalid cashier header data.")

        cash_account_selected = cs_header_data[0]["cash_account_selected"]
        memo = cs_header_data[0]["memo"]
        transaction_date = cs_header_data[0]["date"]
        cash_account_balance = cs_header_data[0]["cash_account_balance"]
        total_cash_count = cs_header_data[0]["total_cash_count"]

        if (
            cash_account_selected == ""
            or cash_account_selected is None
            or cash_account_selected == 0
        ):
            raise Exception("Cashier Account is required.")       

        if not total_cash_count:
            raise Exception("Total Cash Count is required.")

        account = ChartofAccounts.objects.get(id=cash_account_selected)

        type_cast = Type_Cast()

        cs_header_form = CashierHeaderForm(
            {
                "work": work_object,
                "cash_account": account,
                "cash_account_selected": cash_account_selected,
                "memo": memo,
                "date": transaction_date,
                "transaction_date": transaction_date,
                "cash_account_balance": type_cast.convert_to_float(
                    cash_account_balance
                ),
                "total_cash_count": type_cast.convert_to_float(total_cash_count),
                "user": request.user,
            }
        )

        return cs_header_form
```
### Extracting Cashier Line Object from Request
```python
class CashierItemLineRepo:    

    def extract_cashierline_object_from_request(self, request, cs_header_object, work_id, **kwargs):
        """Extract cashier item line object from request"""

        try:
            cs_line_data = request.POST.get("cs_line_data")
            cs_line_data = json.loads(cs_line_data)
            work_object = Work.objects.get(id=work_id)

            if not cs_line_data:
                messages.error(request, "Invalid cashier item line data.")
                raise Exception("Invalid cashier item line data.")

            cs_line_forms = []

            type_cast = Type_Cast()

            for item in cs_line_data:
                if item["row_empty"] == True:
                    continue
                
                csitemlineid = item.get("itemLineId", 0)
                thousand = type_cast.convert_to_decimal(item["thousand"])
                fivehundered = type_cast.convert_to_decimal(item["fivehundered"])
                twohundred = type_cast.convert_to_decimal(item["twohundred"])
                hundred = type_cast.convert_to_decimal(item["hundred"])
                fifty = type_cast.convert_to_decimal(item["fifty"])
                twenty = type_cast.convert_to_decimal(item["twenty"])
                ten = type_cast.convert_to_decimal(item["ten"])
                five = type_cast.convert_to_decimal(item["five"])
                coin = type_cast.convert_to_decimal(item["coin"])
                line_total = type_cast.convert_to_decimal(item["line_total"])   
                memo = item["memo"]             

                cs_line_form = CashierItemLineForm(
                    {
                        "csitemlineid":csitemlineid,
                        "work":work_object,
                        "header":cs_header_object,
                        "thousand":thousand,
                        "five_hundred":fivehundered,
                        "two_hundred":twohundred,
                        "one_hundred":hundred,
                        "fifty":fifty,
                        "twenty":twenty,
                        "ten":ten,
                        "five":five,
                        "one":coin,
                        "line_total":line_total,
                        "memo":memo,
                    }
                )

                cs_line_forms.append(cs_line_form)                

            return cs_line_forms        
        except Exception as e:           
            errorMessages = e.args[0]
            raise Exception(errorMessages)
```