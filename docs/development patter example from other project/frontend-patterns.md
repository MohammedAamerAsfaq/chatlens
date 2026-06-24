# Frontend Development Guide - Vue.js + Django Hybrid
This guide explains how to work with the unique Vue.js + Django hybrid architecture used in Cellusense ERP.
## Architecture Overview
### 🔀 Hybrid Approach
- **Backend**: Django handles routing, authentication, data processing, and initial page rendering
- **Frontend**: Vue.js (Options API) provides interactivity within Django templates
- **Integration**: Vue components are embedded directly in Django templates, no separate SPA
- Shared transactional line-entry behavior is centralized in reusable voucher-body modules, so one UI change can propagate across Bill, Invoice, Purchase Order, Sales Order, and Sales Return.
### 🔑 Key Characteristics
- Vue.js is loaded directly from static files (no build process)
- Components use ES6 modules
- Django templates provide the structure, Vue adds interactivity
- SmartAdmin theme provides the UI foundation
- Shared post-login navigation is composed of three coordinated surfaces:
  - header previous/next history links
  - left sidebar menu with preserved open parent state
  - sidebar recent-pages box
- Header previous/next behavior is app-managed and session-backed rather than raw browser history.
- Left-nav persistence is handled by the shared script `staticfile/dashboard/navigation_state.js`, loaded from the shared base templates after SmartAdmin scripts.
- Recent-pages and navigation labels should stay aligned with:
  - `dashboard/navigation_history.py`
  - `dashboard/navigation_labels.py`
  - the related header/sidebar templates
### 📁 Project Structure Overview
```
cellusense2/
├── core/                              # Django settings and core project configuration
├── staticfile/                        # Frontend assets (Vue.js components, CSS, JS)
│   ├── component/                     # Reusable Vue.js components
│   │   ├── dashboard/                 # Navigation menu component (currently unused)
│   │   ├── account/                   # Data tables for Chart of Accounts, Ledger, etc.
│   │   ├── cashier/                   # Components for listing cashier entries
│   │   ├── vendor/                    # Components for displaying vendor data in tables
│   │   ├── customer/                  # Components for displaying customer data in tables
│   │   ├── inventory/                 # Components for product listings and IMEI log tables
│   │   ├── procureplus/               # Purchase order listing components
│   │   ├── bill/                      # Components for displaying bill entries
│   │   ├── payment/                   # Components to list vendor bill payments
│   │   ├── refund/                    # Components for returned bill transactions
│   │   ├── invoice/                   # Components to list customer invoices
│   │   ├── receipt/                   # Components to list invoice receipts
│   │   ├── salesreturn/              # Components for returned customer invoices
│   │   ├── reportcenter/              # JasperReports-based reporting components
│   │   ├── tiny_cal/                  # On-focus calculator widget triggered by math keys
│   │   ├── select2/                   # Vue-integrated Select2 dropdown component
│   │   ├── paginator/                 # Custom pagination component
│   │   ├── file_list/                 # Dropzone-based file/photo listing component
│   │   ├── search_filter/            # Search component used within report center
│   │   ├── dropzone_vue/              # Custom Dropzone.js integration for Vue
│   │   ├── mysqlbk_list/              # Component to list MySQL backup files
│   │   ├── format_profile/            # Helper for formatting customer/vendor profiles in tables
│   │   ├── css/                       # Shared CSS used by multiple components
│
│   ├── account/                       # Account module assets
│   │   ├── css/                       # Module-specific styles
│   │   ├── add_update_account_vue.js  # Vue file for adding/updating accounts
│   │   ├── add_update_journal_vue.js  # Vue file for adding/updating journals
│   │   ├── account_list.js            # Component loader for account listings
│   │   ├── journal_list.js            # Component loader for journal listings
│   │   ├── ledger_list.js             # Component loader for ledger listings
│
│   ├── cashier/                       # Cashier module assets
│   │   ├── css/                       # Module-specific styles
│   │   ├── cashier_main.js            # Main Vue component with logic and events
│   │   ├── cashier_template.js        # Vue template for rendering UI
│   │   ├── cashier_data_field.js      # Contains reactive data fields
│   │   ├── cashier_props.js           # Props passed into cashier components
│   │   ├── cashier_computed.js        # Computed properties
│   │   ├── cashier_record_navigation.js # Record navigation logic
│
│   ├── [vendor|customer|inventory|...]/
│       # Other modules (vendor, customer, inventory, etc.) follow the same structure
│
│   ├── salesreturn/                   # Sales return Vue components (mounted via template HTML using <div id="VueAgent">)
│   │   ├── css/                       # Module-specific styles
│   │   ├── add_update_salesreturn_vue.js # Main Vue.js component (mounted via 'VueAgent' div)
│   │   ├── salesreturn_data_field.js  # Defines reactive data fields used in the component
│   │   ├── salesreturn_record_navigation.js # Logic for navigating through record sets
│   │   ├── salesreturn_list_template.js # JavaScript containing template render logic or component bootstrap
│
│   ├── reportcenter/                  # Assets for report generation and export
│
│   ├── utils/                         # Common utility scripts (e.g. type casting)
│
│   ├── settings/                      # Frontend-specific configuration settings
│
│   └── themes/                        # SmartAdmin or other third-party UI themes
│
├── basetemplate/                      # Base templates (e.g. base.html for inheritance)
├── datatable/                         # Custom template tags for DataTables integration
├── workflow/                          # Workflow engine to assign transaction-level work IDs
├── dashboard/                         # Post-login landing dashboard
├── account/                           # Backend for managing chart of accounts and ledgers
├── vendor/                            # Vendor management module
├── bill/                              # Billing module (create/view vendor bills)
├── payment/                           # Manages payment of vendor bills
├── refund/                            # Handles returns to vendors
├── inventory/                         # Inventory management and product tracking
├── procureplus/                       # Manages purchase orders
├── customer/                          # Customer management module
├── receipt/                           # Receives payments from customers
├── salesreturn/                       # Handles customer invoice returns
├── cashier/                           # Cash counting & POS system (planned for future)
├── archive/                           # Archives deleted records for audit/history
├── contact/                           # CRM module (under development)
├── document/                          # Document management system (under development)
└── setting/                           # Backend for global project settings

```
### Device Log Pattern

The current unique-device workflow uses a shared voucher-body popup instead of a separate line editor per transaction.

Key pieces:

- `staticfile/component/voucherbody/*`
  - shared item-line table and modal logic
  - row-level device-id button and popup
- `workflow/models/device_log.py`
  - workflow-backed device-id persistence
  - per-device-row `show_id_on_print` flag, driven from voucher header UI on save
- `workflow/device_log_service.py`
  - shared attach/sync helpers for transactional forms
  - shared work-level print-flag hydration helper for voucher headers
- `inventory/function_views/device_log.py`
  - standalone searchable Device Log grid page

Current transaction coverage:

- Bill
- Invoice
- Purchase Order
- Purchase Order v1
- Sales Order v1
- Sales Return

Print behavior:

- the voucher form header exposes `Show Device Id On Print`
- save pushes that voucher-level choice into `workflow.DeviceLog.show_id_on_print`
- edit mode rehydrates the checkbox from existing device-log rows for the same `work`
- Reportkit prints device IDs only when:
  - the voucher-level print flag is enabled
  - the relevant Reportkit config also enables device-id display
- Reportkit placement/label is controlled centrally through `business.ReportkitConfig`

Current gap:

- Refund / Purchase Return still uses its own bill-style payload flow and is not yet wired into the shared device-log popup and hydration path

### Example used in this project
The example used in this project is a Django-based web application for helping users working as cashiers at POS systems. It presents user with a form to count physical cash. It can also connects directly with cash asset account associated with the current user to get its current balance for reconciliation with the physical cash count. It provides record navigation feature and a grid-view of existing records for historical data.
### Template Development
#### 1. [Template Structure](/cashier/templates/cashier/cashier.html)
Every vue-enabled template follows this pattern:
```html

{% extends 'basetemplate/panel_child_template_noform.html' %}
{% load static %}
{% load i18n %}
{% block page_title %}
<title>Cash Register</title>
{% endblock page_title %}
<!-- .................... Header Css Reference .................... -->
{% block header_css_reference %}
<!-- Datatables custom stylesheet by SmartAdmin -->
<!-- To enable localization of Datatables plugin Smartadmin offers seperate file with -rtl suffix. -->
<!-- select2 css -->
<link rel="stylesheet" media="screen, print"
    href="{% static 'themes/smartadmin/css-rtl/formplugins/select2/select2.bundle' %}{{ rtl_value }}" />
<!-- spinner classes -->
<link rel="stylesheet" media="screen, print" href="{% static 'spinner_css/spinkit.css' %}" />
<!-- list view / grid view component :- action columns button style classes -->
<link rel="stylesheet" media="screen, print" href="{% static 'component/css/grid_action_buttons.css' %}" />
<!-- common css used in entire app in addition to theme classes -->
<link rel="stylesheet" media="screen, print" href="{% static 'component/css/common.css' %}" />
<!-- css classes specific to this app -->
<link rel="stylesheet" media="screen, print" href="{% static 'cashier/css/cashier.css' %}" />
{% endblock header_css_reference %}
<!-- .................... End of Header Css Reference .................... -->
<!-- <<<<<<<<<<<<<<<<<<<< Header JS Reference >>>>>>>>>>>>>>>>>>>>>>>>>>> -->
{% block header_js_reference %}
<!-- js file which contains main vue_js component -->
<script type="module" src="{% static 'cashier/cashier_main.js' %}"></script>
<!-- reference axios -->
<script src="{% static 'libraries/axios.min.js' %}"></script>
{% endblock header_js_reference %}
<!-- <<<<<<<<<<<<<<<<<<<< End of Header JS Reference >>>>>>>>>>>>>>>>>>>>>>>>>>> -->
<!-- .................... Heading Panel ........................... -->
<!-- .................... End of Heading Panel .................... -->
<!-- <<<<<<<<<<<<<<<<<<<< Heading Action Button >>>>>>>>>>>>>>>>>>>>>>>>>>> -->
{% block panel_action_buttons %}
<!-- in this section we can place any control which we want to appear beside (close/min/max) button panel -->
{% endblock panel_action_buttons %}
<!-- <<<<<<<<<<<<<<<<<<<< End of Heading Action Button >>>>>>>>>>>>>>>>>>>>>>>>>>> -->
<!-- .................... Main Child Panel ........................... -->
{% block child_panels %}
<!-- specifying data attribute like data-panel-color data-panel-reset data-panel-refresh is disabling it -->
<h5 class="bg-info-900 show-below-300"><strong>Media Not Supported</strong></h5>
<div v-cloak id="VueAgent">
    <div id="panel-customer" class="panel hide-below-300" data-panel-color data-panel-reset data-panel-refresh>       
        <!-- template loader file -->
        <!-- cashier_template is name of template tag file. -->
        {% load cashier_template %}
        <!-- this is coming from same project folder -->
        <!-- this is debug file section, it exposes vue data properties for inspection and debugging switching - show_selected_ids -->
        {% call_cashier_debug_data rtl_value selected_theme %}

        <div  class="panel-hdr bg-faded">
            <i class="fal fa-cash-register fa-2x"></i>&nbsp;<i class="fal fa-edit"></i>&nbsp;&nbsp;
            
            <h2 class="fw-700 fs-xl">
                {% if opp == 'add' %}
                    {% translate ' Add Cashcount' %}
                {% else %}
                    {% translate ' Update Cashcount' %}
                {% endif %}
            </h2> 

            <!-- This record navigation control -->
            {% call_cashier_navigation_panel rtl_value selected_theme %}

            <!-- body content_setting is coming from utils project -->
            <!-- its a drop down control on the left of panel-header, it lists few controls for debugging, show_selected_ids is also listed here -->
            {% load body_content_setting %}
            {% call_body_content_setting rtl_value selected_theme %}           
            
        </div>
       
        <!-- to pass django template data to vue data properties -->
        <span hidden=true>[[oppForDisplay="{{ opp }}"]]</span>
        <span hidden=true>[[save_url="{{ save_url }}"]]</span>
        <span hidden=true>Cashier Header Id is -- [[cs_header_id_for_display="{{ cs_header_id }}"]]</span>
        <span hidden=true>Cashier Auto Number is --
            [[cs_auto_number_for_display="{{ cs_header_id }}"]]</span>
        <span hidden=true>Cashier Next Estimated Id --
            [[next_estimated_id_for_display="{{ cs_header_id }}"]]</span>
        
        <!-- Panel Container Body -->
        <div class="panel-container show">
            <!-- Loading spinner div -->
            <div class="sk-circle sk-center loading-spinner-center" v-if="loading">
                <div class="sk-circle-dot"></div>
                <div class="sk-circle-dot"></div>
                <div class="sk-circle-dot"></div>
                <div class="sk-circle-dot"></div>
                <div class="sk-circle-dot"></div>
                <div class="sk-circle-dot"></div>
                <div class="sk-circle-dot"></div>
                <div class="sk-circle-dot"></div>
                <div class="sk-circle-dot"></div>
                <div class="sk-circle-dot"></div>
                <div class="sk-circle-dot"></div>
                <div class="sk-circle-dot"></div>
            </div>
            <!-- form control -->
            <form id="childForm" name="childForm" @submit="handleSubmit">
                <!-- Form Begins -->
                <!-- Panel Container Content -->
                <div class="panel-content" :class="{ 'blur-when-loading': loading }">
                    {% csrf_token %}
                    <!-- parentDataLoaded vue data property is used to make sure all properties are properly initialized before showing up on UI -->
                    <div v-if="parentDataLoaded" class="panel-content">                       
                        
                        <!-- this is coming from utils project. -->
                        <!-- common validation errors coming from ajax page itself and ajax request -->
                        {% load form_validation_errors %}
                        {% call_form_validation_errors rtl_value selected_theme %}

                        <!-- this is coming from utils project. -->
                        <!-- validation errors comming from django views which returns result other than json -->
                        {% load server_errors %}
                        {% call_server_errors rtl_value selected_theme %}       

                        <div class="row d-flex flex-wrap form-group" v-for="(rec, index) in cs_header_data" :key="rec.id">

                            <div id="cashier_header_memo" class="col-md-2 d-flex flex-column">
                                <label class="form-label fw-500">{% translate 'Id' %}</label>
                                <div  class="input-group">
                                    <input type="text" class="form-control" v-model="rec.id" placeholder="{% translate 'Id' %}" />                                
                                </div>
                            </div>  
                            <!-- select2 component configured to use with vue_js -->
                            <div id="cashier_header_account" class="col-md-3">
                                <label class="form-label fw-500">{% translate 'Select Cash Account' %}</label>
                                <div class="input-group" :style="css_cs_account_id_invalid">
                                    <select2-component name="cash_account_selected" id="cash_account_selected"
                                                    data-select2-id="id_cashaccount" :url="'/cashier/get_cashiers_cash_account'"
                                                    :minimumInputLength="3" tabindex="1" :placeholder="'Search Account...'"
                                                    :prop_id="rec.cash_account_object.id" :prop_text="rec.cash_account_object.text"
                                                    v-model="rec.cash_account_selected" :options="rec.cash_account_object" tabindex="1"
                                                    @child-event-item-id="childEventSelectedCashAccountId($event, index)"
                                                    @child-event-item-text="childEventSelectedCashAccountText($event, index)">
                                    </select2-component>
                                </div>
                            </div>  
    
                            <div id="cashier_header_memo" class="col-md-5 d-flex flex-column">
                                <label class="form-label fw-500">{% translate 'Memo' %}</label>
                                <div  class="input-group">
                                    <input type="text" class="form-control" v-model="rec.memo" placeholder="{% translate 'Memo' %}" tabindex="2"/>                                
                                </div>
                            </div>  

                            <div id="cashier_header_memo" class="col-md-2 d-flex flex-column">
                                <label class="form-label fw-500">{% translate 'Date' %}</label>
                                <div  class="input-group">
                                    <input type="date" class="form-control" v-model="rec.date" placeholder="{% translate 'Date' %}" tabindex="3"/>
                                </div>
                            </div>
                        </div>                       
                        <!-- line data component customized for this app -->
                        <cashier-component 
                            v-model="cs_line_data"
                            :model_value_header_data="cs_header_data"
                            :model_value_existing_lines="cs_line_data_existing_data"
                            :model_value_deleted_lines="cs_line_data_deleted_data"
                            :editing_mode_on="editing_mode_on" 
                            :validation_tick_class="validationTick"
                            :validation_tick_class_red="validationRed" 
                            :show_selected_ids="show_selected_ids"                                                                                    
                            :css_item_line_invalid="css_item_line_invalid"                             
                            ref="childRefImeiLog" tabindex="-1"
                            @child-event-total-cash-count="total_cash_count_catchevent($event, value)">
                        </cashier-component>

                        <div class="d-flex align-items-right form-group">
                            <strong class="form-label fw-700 fs-xl">Total Cash Count:</strong>&nbsp;&nbsp;<span v-if="cs_header_data[0].total_cash_count!=0" :class="class_final_total">[[cs_header_data[0].total_cash_count]]</span>
                        </div>

                        <div class="d-flex align-items-right form-group">
                            <strong class="form-label fw-700 fs-xl">Cash Account Balance:</strong>&nbsp;&nbsp;<span v-if="cs_header_data[0].cash_account_balance!=0" :class="class_final_total">[[cs_header_data[0].cash_account_balance]]</span>
                        </div>

                        <div class="d-flex align-items-right form-group">
                            <strong class="form-label fw-700 fs-xl">Difference:</strong>&nbsp;&nbsp;<span :class="class_final_total">[[cs_header_data[0].total_cash_count - cs_header_data[0].cash_account_balance]]</span>
                        </div>
                      
                    </div>
                    <div
                        class="d-flex align-items-right panel-content py-2 rounded-bottom  border border-faded border-left-0 border-right-0 border-bottom-1 text-muted">
                        <button title="Save" id="savenew" type="submit"
                            class="btn btn-sm btn-outline-primary mr-2 waves-effect waves-themed"
                            :disabled="isSaveButtonDisabled">
                            <span :class="submitButtonSpinnerClass" role="status"
                                aria-hidden="true"></span>{% translate 'Save & New' %}
                        </button>
                        <button title="SaveClose" id="saveclose" type="submit"
                            class="btn btn-sm btn-outline-primary mr-2 waves-effect waves-themed"
                            :disabled="isSaveButtonDisabled">
                            <span :class="submitButtonSpinnerClass" role="status"
                                aria-hidden="true"></span>{% translate 'Save & Close' %}
                        </button>
                    </div>
                </div>
            </form>
            <!-- This is coming from utils project. -->
            {% load modal_delete_confirmation %}
            <!-- confirmation control for delete action -->
            {% call_modal_delete_confirmation rtl_value selected_theme %}
            <!-- confirmation control for save action -->
            {% call_modal_action_confirmation rtl_value selected_theme %}            

            <!-- Form Ends -->
            
            <!-- Test Zone -->
            <!-- this is a helper to try/debug new and existing features -->
            <!-- an other alternative to console.log -->
            <div v-if="show_selected_ids">
                <button title="Save" id="test" type="test"
                    class="btn btn-primary btn-pills waves-effect waves-themed mr-3" @click="test()">
                    <span :class="submitButtonSpinnerClass" role="status"
                        aria-hidden="true"></span>{% translate 'Test' %}
                </button>
            </div>
            <!-- End of Test Zone -->

        </div>

    </div>  
     <div id="panel-1" class="panel hide-below-300">
        <!-- this custom component is designed to lists existing entries -->
        <div class="panel-hdr bg-faded">
            <i class="fal fa-envelope-open-dollar fa-2x"></i>&nbsp;<i class="fal fa-list"></i>&nbsp;&nbsp;
            <h2 class="fw-700 fs-xl">{% translate 'List of Cash Counts' %}</h2>
        </div>
        <div class="panel-container show">
            <div class="panel-content">
                <!-- This loading is required, as some files needed for datables in included in this template tag. -->
                {% load datatable_main %}
                {% call_datatable_main rtl_value selected_theme %}
                {# djlint:off #}
                <cs-list id="cslist" 
                    :url='"{% url 'cashier:grid-view' %}"'
                    :edit_button="true" 
                    :delete_button="true"
                    :child_row_button="true" 
                    :report_button="true" 
                    :create_button="true" 
                    :editor_url='"/cashier/operation/update/"'
                    :row_edit_url='"/cashier/operation/update/"'
                    :receipt_history_url='"/cashier/history/"' 
                    :delete_url='"/cashier/delete/"'
                    :child_row_url='"/cashier/get_cs_child_row/"' 
                    :ledger_report_url='"/account/ledger_report/"'
                    :csrf_token="'{{ csrf_token }}'" 
                    v-model="reloadCSList_byAccountId"
                    :reload_cs_list="reloadCSList"
                    :rowsLength="5" 
                    :redirect="!scroll_up_on_edit" 
                    @child-event-delete-row="childEventCSListSelectedRowIdforDelete($event, index)"  
                    @child-event-report-row="childEventCSListSelectedRowIdforReport($event, index)"         
                >
                </cs-list>          

                {# djlint: on #}

            </div>
        </div>
    </div>  
</div>
<style></style>
{% endblock child_panels %}
<!-- .................... End of Main Child Panel ........................... -->
{% block script_at_the_end %}
<!-- this script is needed for child record of grid view -->
<script src="{% static 'component/cashier/cashier_item_list_format_child_row.js' %}"></script>
{% endblock script_at_the_end %}

```
##### 1a. Template Tag for Debugging and Testing - [cashier_debug_data](/cashier/templates/cashier_debug_data.html)
```html
{% load static %}
{% load i18n %}

<div v-if="show_selected_ids">
    <div class="col-md-12">
        <label for="id_account_name" class="form-label">
            {% translate 'Ajax Data Received' %}
        </label>
        <h5>Cashier header data</h5>
        <div class="row d-flex flex-no wrap bd-highlight bg-primary-50">
            [[cs_header_data]]
        </div>        
        <h5>Cashier Item Line data</h5>
        <div v-for="(rec, index) in cs_line_data"
            class="row d-flex flex-wrap bg-success-50">
            <div>[[index]] - [[rec]]</div>
        </div>
        <h5>Cashier Item Line Existing data</h5>
        <div v-for="(rec, index) in cs_line_data_existing_data"
            class="row d-flex flex-wrap bg-success-500">
            <div>[[index]] - [[rec]]</div>
        </div>
        <h5>Deleted Data from Items</h5>
        <div v-for="(rec, index) in cs_line_data_deleted_data"
            class="row d-flex flex-wrap">
            <div>[[index]] - [[rec]]</div>
        </div>        
    </div>    
    <div class="d-flex flex-wrap mt-2 bd-highlight">        
        <p>Save URL is: [[ save_url ]]</p>
        ||
        <p>Cashier Id is: [[ cs_header_id ]]</p>
        ||
        <p>Opp for Display: [[ oppForDisplay ]]</p>
        ||
        <p>Opp is: [[ opp ]]</p>
        ||
        <p>Is Loading: [[loading]]</p>
        ||
        <p>Is Save Button Disabled: [[isSaveButtonDisabled]]</p>
        ||
        <p>Is Scroll Up on Edit: [[scroll_up_on_edit]]</p>
        ||
        <p>Show Error: [[showError]]</p>
        ||
        <p>Is Form Valid: [[is_form_valid]]</p>
        ||
        <p>Is 2 Rows Valid: [[is_2_rows_valid]]</p>
        ||
        <p>Number of Rows Valid: [[number_of_rows_valid]]</p>        
    </div>
    <div v-show="is_form_valid" class="bg-success-500">
        Yess!! Form is Valid....
    </div>
</div>
```
##### 1b. Template Tag for Record Navigation Control - [cashier_navigation_panel](/cashier/templates/cashier_navigation_panel.html)
```html
{% load static %}
{% load i18n %}
<div class="d-flex justify-content-start align-items-center"> 
    <div class="order-1">       
        <button type="button" class="btn btn-outline-primary waves-effect waves-themed mr-2 d-none d-xl-block"
            @click="newRecord">
            {% translate 'New' %}
            <i class="fal fa-edit"></i>
        </button>
        <button type="button" class="btn btn-outline-primary waves-effect waves-themed mr-2 d-xl-none"
            @click="newRecord">
            <i class="fal fa-edit"></i>
        </button>
    </div>
    <div class="d-none d-md-block order-1"
        v-if="cs_header_data[0] && cs_header_data[0].id != undefined">
        <div id="recordNavigationdiv" class="input-group">
            <div class="input-group-prepend">
                <button class="btn btn-sm btn-outline-primary" type="button" @click="previousRecord">
                    <i class="fal fa-angle-left"></i>
                </button>
            </div>
            <input type="text" class="form-control text-center" v-model="cs_header_data[0].id"
                @blur="changeRecord">
            <div class="input-group-append">
                <button class="btn btn-sm btn-outline-primary" type="button" @click="nextRecord">
                    <i class="fal fa-angle-right"></i>
                </button>
            </div>
        </div>
    </div>
    <!-- show here icon of document attachment (clip) -->    
    <div class="input-group-append order-4">
        <a href="javascript:void(0);" class="header-icon">
            <i class="fal fa-paperclip"></i>
            <span v-if="numberOfDocs>0" class="badge badge-icon pos-top pos-right">[[ numberOfDocs ]]</span>
        </a>
    </div>
    <!-- show print button here -->
    <div class="input-group-append order-5">
        <a href="#" class="header-icon" type="button" @click="printVoucher('pdf')">
            <i class="fal fa-2x fa-file-pdf"></i>
        </a>
        <a href="#" class="header-icon" type="button" @click="printVoucher('html')">
            <i class="fal fa-2x fa-file-invoice"></i>
        </a>
        <a href="#" class="header-icon" type="button" @click="printVoucher('print')">
            <i class="fal fa-2x fa-print"></i>
        </a>
    </div>
</div>
```
##### 1c. Template Tag for Header Panel Settings - [panel_header_settings](/utils/templates/body_content_setting.html)
```html
{% load static %}
{% load i18n %}
<ul class="nav nav-pills border-bottom-0 d-none d-md-block" role="tablist">
    <li class="nav-item dropdown">
        <a class="nav-link dropdown-toggle" data-toggle="dropdown" href="#" role="button"
            aria-haspopup="true" aria-expanded="false">{% translate 'Settings' %}</a>
        <div class="dropdown-menu">
            <label class="dropdown-item">
                <input type="checkbox" @click="toggle" class="form-checkbox h-5 w-5 text-gray-600"
                    :checked="show_selected_ids" />
                <span class="ml-2 text-gray-700">Show Selected Ids</span>
            </label>
            <label class="dropdown-item">
                <input type="checkbox" @click="toggleMultiCurrency" class="form-checkbox h-5 w-5 text-gray-600"
                    :checked="enable_multicurrency" />
                <span class="ml-2 text-gray-700">Multi Currency</span>
            </label>
            <label for="scrolluponedit" class="dropdown-item">
                <input type="checkbox" id="scrolluponedit" @click="toggleScrollUpOnEdit"
                    class="form-checkbox h-5 w-5 text-gray-600" :checked="scroll_up_on_edit" />
                <span class="ml-2 text-gray-700">Scroll Up on Edit</span>
            </label>
            <label for="toggleSpinner" class="dropdown-item">
                <input type="checkbox" id="toggleSpinner" @click="toggleLoading"
                    class="form-checkbox h-5 w-5 text-gray-600" :checked="loading" />
                <span class="ml-2 text-gray-700">Activate Spinner</span>
            </label>
            <label for="toggleFocusOnTab" class="dropdown-item">
                <button type="button" id="toggleFocusOnTab" @click="toggleFocusOnTab"
                    class="btn btn-primary btn-pills waves-effect waves-themed mr-3">Change Focus on
                    Tab</button>
            </label>
            <label for="compareArrays" class="dropdown-item">
                <button type="button" id="compareArrays" @click="compareArrays"
                    class="btn btn-primary btn-pills waves-effect waves-themed mr-3">Compare Arrays</button>
            </label>
            <label for="Test" class="dropdown-item">
                <button type="button" id="Test" @click="Test"
                    class="btn btn-primary btn-pills waves-effect waves-themed mr-3">Test</button>
            </label>
            <label for="getexchangerate" class="dropdown-item">
                <button type="button" id="Test" @click="getExchangeRate"
                    class="btn btn-primary btn-pills waves-effect waves-themed mr-3">Get Exchange Rate</button>
            </label>
        </div>
    </li>
</ul>
```
##### 1d. Template Tag for Save Action Confirmation - [save_action_confirmation](/utils/templates/modal_action_confirmation.html)
```html
<div class="modal fade action-confirmation-modal" tabindex="-1" role="dialog" aria-hidden="true">
    <div class="modal-dialog modal-dialog-centered modal-transparent" role="document">
        <div class="modal-content">
            <div class="modal-header">
                <h4 class="modal-title text-white">
                    [[action_confirmation_title]]
                    <small class="m-0 text-white opacity-70">
                        [[action_confirmation_question_title]]
                    </small>
                </h4>
                <button type="button" class="close text-white" data-dismiss="modal" aria-label="Close">
                    <span aria-hidden="true"><i class="fal fa-times"></i></span>
                </button>
            </div>
            <div class="modal-body">
                ...
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-dismiss="modal" @click="resetFormValidationErrors()">[[action_confirmation_NO_title]]</button>
                <button type="button" class="btn btn-primary" @click="do_action()">[[action_confirmation_YES_title]]</button>
            </div>
        </div>
    </div>
</div>
```
##### 1e. Template Tag for Delete Action Confirmation - [save_action_confirmation](/utils/templates/modal_delete_confirmation.html)
```html
<div class="modal fade example-modal-centered-transparent" tabindex="-1" role="dialog" aria-hidden="true">
    <div class="modal-dialog modal-dialog-centered modal-transparent" role="document">
        <div class="modal-content">
            <div class="modal-header">
                <h4 class="modal-title text-white">
                    Deleting Record...
                    <small class="m-0 text-white opacity-70">
                        Are you sure you want to delete this record?
                    </small>
                </h4>
                <button type="button" class="close text-white" data-dismiss="modal" aria-label="Close">
                    <span aria-hidden="true"><i class="fal fa-times"></i></span>
                </button>
            </div>
            <div class="modal-body">
                ...
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-dismiss="modal">Close</button>
                <button type="button" class="btn btn-primary" @click="deleteRecord()">Yes, Delete It.</button>
            </div>
        </div>
    </div>
</div>
```
#### 2. Vue Component Structure
App-specific vue main js file in [Main_Vue_Container](/staticfile/cashier/cashier_main.js)
```javascript
import { createApp } from "/static/libraries/vue.app.js";
//import components
import Select2Preloaded from "/static/component/select2/select2_vue_preload.js";
import Select2Component from "/static/component/select2/select2_vue.js";
import TinyCal from "/static/component/tiny_cal/tiny_cal.js";
import { cashierDataField } from "./cashier_data_field.js";
import { cashierComputed } from "./cashier_computed.js";
import { cashierProps } from "./cashier_props.js";
import { recordNavigation } from "./cashier_record_navigation.js";
import CashierComponent from "/static/component/cashier/cashier_component_main.js";
import CsList from "/static/component/cashier/cashier_list_component.js";

createApp({
  //to avoid conflict with django template which uses {{}}, we use [[ ]] for vue js
  //because vue js also uses {{}} for binding data by default
  delimiters: ["[[", "]]"],
  components: {
    //**************************select 2 component with preloaded options***
    Select2Preloaded,
    //**************************select 2 component***************************
    Select2Component,
    //**************************tiny cal component***************************
    TinyCal,
    //**************************cashier component***************************
    CashierComponent,
    //**************************cashier list component***************************
    CsList,
  },
  props: cashierProps,
  data() {
    return cashierDataField();
  },
  mounted() {
    this.initialize(this.cs_header_id_for_display, this.oppForDisplay);
  },
  methods: {
    initialize(_cs_header_id, _opp) {
      let self = this;

      self.parentDataLoaded = false;
      self.cs_header_data = [];
      self.cs_line_data = [];
      self.cs_line_data_existing_data = [];
      self.cs_line_data_deleted_data = [];

      const cs_header_id = _cs_header_id;
      self.opp = _opp;

      if (self.opp == "add") {
        self.cs_header_data.push({
          id: cs_header_id,
          cash_account_object: { id: 0, text: "" },
          cash_account_selected: 0,
          memo: "",
          date: new Date().toISOString().slice(0, 10),
          cash_account_balance: 0,
          total_cash_count: 0,
        });

        // push 10 empty rows
        for (let i = 0; i < 10; i++) {
          self.cs_line_data.push({
            line_index: i,
            itemLineId: 0,
            thousand: 0,
            fivehundered: 0,
            twohundred: 0,
            hundred: 0,
            fifty: 0,
            twenty: 0,
            ten: 0,
            five: 0,
            coin: 0,
            line_total: 0,
            memo: "",
            row_empty: false,
            row_deleted: false,
            row_changed: false,
          });
        }
        self.parentDataLoaded = true;
        return;
      }
      self.getDataFromServer(cs_header_id);
    },
    getDataFromServer(csHeaderId) {
      let self = this;
      axios({
        method: "get",
        url: "/cashier/get_cashier_data_from_server/" + csHeaderId,
      })
        .then((response) => {
          const _cs_header_data = response.data.cs_header_data;

          if (_cs_header_data.length === 0) {
            // No existing record found so return from here
            self.parentDataLoaded = true;
            return;
          }

          if (_cs_header_data.length > 0) {
            self.cs_header_data = [];
            self.cs_line_data = [];
            self.cs_line_data_existing_data = [];
            self.cs_line_data_deleted_data = [];

            const _cs_line_data = response.data.cs_line_data;

            self.cs_header_data.push({
              id: _cs_header_data[0].id,
              cs_header_id: _cs_header_data[0].id,
              cash_account_object: {
                id: _cs_header_data[0].cash_account_object.id,
                text: _cs_header_data[0].cash_account_object.text,
              },
              cash_account_selected: _cs_header_data[0].cash_account_object.id,
              cash_account_balance: _cs_header_data[0].cash_account_balance,
              total_cash_count: _cs_header_data[0].total_cash_count,
              date: _cs_header_data[0].transaction_date,
              memo: _cs_header_data[0].memo,
            });

            this.childEventSelectedCashAccountId(
              _cs_header_data[0].cash_account_object.id
            );

            _cs_line_data.forEach((line) => {
              self.cs_line_data.push({
                line_index: line.line_index,
                itemLineId: line.id,
                thousand: line.thousand,
                fivehundered: line.five_hundred,
                twohundred: line.two_hundred,
                hundred: line.one_hundred,
                fifty: line.fifty,
                twenty: line.twenty,
                ten: line.ten,
                five: line.five,
                coin: line.one,
                line_total: line.line_total,
                memo: line.memo,
                row_empty: false,
                row_deleted: false,
                row_changed: false,
              });
            });
          }

          self.parentDataLoaded = true;
        })
        .catch((error) => {
          this.errorMessage = get_messages_ajax_error(error);
          this.showError = true;
        });
    },
    childEventSelectedCashAccountId(value) {      
      if (value == 0 || value == null || value == "" || value == undefined) {
        return;
      }
      this.cs_header_data[0].cash_account_object.id = value;
      this.reloadCSList_byAccountId = value;
    },
    childEventSelectedCashAccountText(value) {      
      this.cs_header_data[0].cash_account_object.text = value;      
    },
    childEventCSListSelectedRowIdforDelete(value) {      
      this.delete_url = value;
    },    
    resetFormValidationErrors() {
      this.formValidationErrors = [];
      this.inputControlClassforTextBox = "form-control border";
      this.css_cs_header_id_invalid = "";
      this.css_item_line_invalid = "";
      this.css_cs_account_id_invalid = "";
      this.number_of_rows_valid = 0;
      this.loading = false;
    },
    resetServerErrors() {
      // this is to reset server side errors, that are displayed on top of the page
      // after page is submitted and error is returned from server
      this.errorMessage = "";
      this.showError = false;
    },   
    newRecord() {
      window.location.href = "/cashier/operation/add/0";
    },
    async previousRecord() {
      const previous_cs_id = await recordNavigation.previousRecord(
        this.cs_header_data
      );
      if (
        previous_cs_id != null &&
        previous_cs_id != undefined &&
        previous_cs_id != "" &&
        previous_cs_id != 0
      ) {
        this.initialize(previous_cs_id, "update");
      }
    },
    async nextRecord() {
      const next_cs_id = await recordNavigation.nextRecord(this.cs_header_data);
      if (
        next_cs_id != null &&
        next_cs_id != undefined &&
        next_cs_id != "" &&
        next_cs_id != 0
      ) {
        this.initialize(next_cs_id, "update");
      }
    },
    toggle() {
      // this is to toggle show_selected_ids
      this.show_selected_ids = !this.show_selected_ids;
    },    
    toggleLoading() {
      this.loading = !this.loading;
    },
    total_cash_count_catchevent(value) {      
      this.cs_header_data[0].total_cash_count = value;
    },
    handleSubmit(event) {
      event.preventDefault();

      this.resetFormValidationErrors();

      this.cs_line_data.forEach((line) => {
        if (line.line_total != 0) {
          this.number_of_rows_valid += 1;
        }
      });

      const isItemLineValid = this.number_of_rows_valid >= 1;
      if (!isItemLineValid) {
        this.formValidationErrors.push(
          "Atleast 1 valid row of count is required."
        );
        this.css_item_line_invalid =
          "border:2px solid #fd3995;border-radius:3px;";
      }

      const isIdValid =
        this.cs_header_data[0].id !== "" &&
        this.cs_header_data[0].id !== null &&
        this.cs_header_data[0].id !== undefined &&
        this.cs_header_data[0].id !== 0;

      if (!isIdValid) {
        this.formValidationErrors.push("Id is required.");
        this.css_cs_header_id_invalid =
          "border:2px solid #fd3995;border-radius:3px;";
      }

      const isCashAccountValid =
        this.cs_header_data[0].cash_account_selected !== 0 &&
        this.cs_header_data[0].cash_account_selected !== null &&
        this.cs_header_data[0].cash_account_selected !== undefined &&
        this.cs_header_data[0].cash_account_selected !== "";

      if (!isCashAccountValid) {
        this.formValidationErrors.push("Cash Account is required.");
        this.css_cs_account_id_invalid =
          "border:2px solid #fd3995;border-radius:3px;";
      }

      this.is_form_valid = isItemLineValid && isIdValid && isCashAccountValid;

      //if form is not valid, then enable save button and return
      if (!this.is_form_valid) {
        this.loading = false;
        //enable save button
        this.isSaveButtonDisabled = false;
        //hide spinner on submit button
        this.submitButtonSpinnerClass = "";
        $("html, body").animate({ scrollTop: 0 }, "slow");
        return;
      }

      this.confirm_action(event);
    },
    confirm_action(sender) {
      $(".action-confirmation-modal").modal("show");

      if (sender.submitter.id === "savenew") {
        this.action_confirmation_title = "Save & New";
        this.action_confirmation_question_title =
          "Are you sure you want to save and new IMEI Log?";
        this.action_confirmation_NO_title = "No, Cancel";
        this.action_confirmation_YES_title = "Yes, Save & New";
        this.action_confirmation_sender = sender;
      }

      if (sender.submitter.id === "saveclose") {
        this.action_confirmation_title = "Save & Close";
        this.action_confirmation_question_title =
          "Are you sure you want to save and close IMEI Log?";
        this.action_confirmation_NO_title = "No, Cancel";
        this.action_confirmation_YES_title = "Yes, Save & Close";
        this.action_confirmation_sender = sender;
      }

      $(".action-confirmation-modal").modal("show");
    },
    do_action() {
      if (
        this.action_confirmation_sender === "" ||
        this.action_confirmation_sender === null
      ) {
        return;
      }

      if (this.action_confirmation_sender.submitter.id === "savenew") {
        this.process_save(this.action_confirmation_sender);
      }

      if (this.action_confirmation_sender.submitter.id === "saveclose") {
        this.process_save(this.action_confirmation_sender);
      }

      $(".action-confirmation-modal").modal("hide");
    },
    process_save(event) {
      let self = this;
      let formData = new FormData(event.target);
      // append cashier_header_data to form data
      formData.append("cs_header_data", JSON.stringify(this.cs_header_data));
      // remove empty lines from cashier_line_data
      this.cs_line_data = this.cs_line_data.filter((line) => {
        return line.line_total != 0;
      });
      // append cashier_line_data to form data
      formData.append("cs_line_data", JSON.stringify(this.cs_line_data));

      formData.append(
        "cs_line_data_existing_data",
        JSON.stringify(this.cs_line_data_existing_data)
      );

      formData.append(
        "cs_line_data_deleted_data",
        JSON.stringify(this.cs_line_data_deleted_data)
      );

      if (self.opp == "add") {
        self.save_url = "/cashier/save/0/add";
      } else {
        self.save_url =
          "/cashier/save/" + self.cs_header_data[0].id + "/update";
      }

      //submit form
      axios
        .post(self.save_url, formData, {
          headers: {
            "X-CSRFToken": this.csrf_token,
            "Content-Type": "application/json",
          },
        })
        .then((response) => {
          this.successMessage = response.data.messages;
          this.showSuccess = true;

          get_messages_ajax(response.data.json_data);

          if (event.submitter.id == "saveclose") {
            window.location.href = "/dashboard/";
          } else {
            this.initialize(0, "add");
            // scroll to top
            $("html, body").animate({ scrollTop: 0 }, "slow");
          }
          if (self.reloadCSList) {
            self.reloadCSList = false;
          } else {
            self.reloadCSList = true;
          }
        })
        .catch((error) => {
          this.errorMessage = get_messages_ajax_error(error);
          this.showError = true;
        })
        .finally(() => {
          this.isSaveButtonDisabled = false;
          this.submitButtonSpinnerClass = "";
          this.loading = false;
        });
    },
    deleteRecord() {
      let self = this;
      $(".example-modal-centered-transparent").modal("hide");

      $.ajax({
        url: self.delete_url,
        type: "POST",
        headers: {
          "X-CSRFToken": self.csrf_token,
        },
        dataType: "json",
        success: function (data, textStatus, jqXHR) {
          if (self.reloadSRList) {
            self.reloadCSList = false;
          } else {
            self.reloadCSList = true;
          }
          get_messages_ajax(data.json_data);          
        },
        error: function (xhr, error, thrown) {          
          get_messages();
        },
      });
    },
    changeRecord() {},
    getExchangeRate() {},
    toggleFocusOnTab() {},
    compareArrays() {},
    toggleMultiCurrency() {},
    toggleScrollUpOnEdit() {},
    childEventCSListSelectedRowIdforReport(value) {},    
    Test() {},
  },
  computed: cashierComputed,
  watch: {},
}).mount("#VueAgent");

```
#### Runtime Standard

- Vue module pages should import Vue from `/static/libraries/vue.app.js`.
- Use `/static/libraries/vue.dev.js` only when a page intentionally needs the development runtime for local debugging.
- Browser-loaded Axios should come from `{% static 'libraries/axios.min.js' %}`.
- Do not add new CDN runtime dependencies for Vue or Axios in live templates.
### Reusable Components
#### 1. Creating Reusable Components
Place reusable components in `staticfile/component/{componentname}`:
Create seperate js files for main, props, datafield, computed and template.
Name the main file as appname_component_main.js
Name the props file as appname_component_props.js
Name the data field file as appname_component_data_field.js
Name the computed file as appname_component_computed.js
Name the template file as appname_component_template.js

```javascript
import Select2Preloaded from "/static/component/select2/select2_vue_preload.js";
import Select2Component from "/static/component/select2/select2_vue.js";
import TinyCal from "/static/component/tiny_cal/tiny_cal.js";
import { cashiercomponentDataField } from "./cashier_component_data_field.js";
import { cashiercomponentComputed } from "./cashier_component_computed.js";
import { cashiercomponentProps } from "./cashier_component_props.js";
import cashiercomponentTemplate from "./cashier_component_template.js";

export default {
  //to avoid conflict with django template which uses {{}}, we use [[ ]] for vue js
  //because vue js also uses {{}} for binding data by default
  delimiters: ["[[", "]]"],
  components: {
    //**************************select 2 component with preloaded options***
    Select2Preloaded,
    //**************************select 2 component***************************
    Select2Component,
    //**************************tiny cal component***************************
    TinyCal,
  },
  template: cashiercomponentTemplate,
  props: cashiercomponentProps,
  data() {
    return cashiercomponentDataField();
  },
  mounted() {
    this.parentDataLoaded = true;
  },
  methods: {
    sample_method(){
      console.log("Test from sample method: " + this.sample_property);
    },
    addRowOnLastLine(index) {
      if (index === this.modelValue.length - 1) {
        this.addRow();
        // set focus on last tow
        this.setFocusOnLastRow(index);
      }
    },
    setFocusOnLastRow(index) {      
      this.$nextTick(() => {
        let lastrow = document.getElementById(`id_form-${index + 1}-thousand`);
        if (lastrow != "undefined" && lastrow != null) {
          lastrow.focus();
        }
      });
    },
    addRow() {
      this.modelValue.push({
        line_index: 0,
        itemLineId: 0,
        thousand: 0,
        fivehundered: 0,
        twohundred: 0,
        hundred: 0,
        fifty: 0,
        twenty: 0,
        ten: 0,
        five: 0,
        coin: 0,
        line_total: 0,
        memo:"",
        row_empty: false,
        row_deleted: false,
        row_changed: false,
      });
    },
    deleteRow(value, line) {
      let index = this.modelValue.indexOf(line);    
      const parent = value.target.parentElement;
      const tr = parent.closest("tr");     
      line.row_deleted = true;
      if (index > -1) {
        this.model_value_deleted_lines.push(this.modelValue[index]);
        this.modelValue.splice(index, 1);
      }    
    },   
    elementName(index, field) {
      // this method is used to generate element name for django formset, can be re-written to use vue formset
      return `form-${index}-${field}`;
    },
    checkValidRows(line) {   
          //  if line total is 0 then row is empty
          line.row_empty = !(line.line_total != 0);        
    },
  },
  computed: cashiercomponentComputed,
  watch: {
    modelValue: {
      handler(newVal) {
        newVal.forEach(line => {
          line.line_total = 
            (parseFloat(line.thousand) || 0) * 1000 +
            (parseFloat(line.fivehundered) || 0) * 500 +
            (parseFloat(line.twohundred) || 0) * 200 +
            (parseFloat(line.hundred) || 0) * 100 +
            (parseFloat(line.fifty) || 0) * 50 +
            (parseFloat(line.twenty) || 0) * 20 +
            (parseFloat(line.ten) || 0) * 10 +
            (parseFloat(line.five) || 0) * 5 +
            (parseFloat(line.coin) || 0) * 1;
            this.checkValidRows(line);
        });
      },
      deep: true, // Ensures Vue watches for changes inside objects
    }
  },
};

```
#### 2. Using Reusable Components
Import and use in your main Vue component:

```javascript
import MyReusableComponent from '/static/component/my_reusable_component.js';

// In your main component
components: {
    'my-reusable-component': MyReusableComponent
},

// In template
<my-reusable-component 
    v-model="formData.selected_value"
    :options="availableOptions"
    placeholder="Choose an option..."
    @child-event-item-selected="handleSelection">
</my-reusable-component>
```
### Customized vue component used in this project - [(Select2 Dropdown Control)](/staticfile/component/select2/select2_vue.js)
```javascript
export default {
    template: `<select class="form-control" :value="modelValue"  
                @input="$emit('update:model-value', $event.target.value)"                 
                ref="select2-vue"></select>`,
    props: {
        modelValue: {
            type: [String, Number, Object],
            required: true
        },
        url: {
            type: String,
            required: true,
        },        
        delay: {
            type: Number,
            default: 250,
        },
        minimum_Input_Length: {
            type: Number,
            default: 0,
        },
        placeholder: {
            type: String,
            default: '',
        },
        allow_clear: {
            type: Boolean,
            default: false,
        },
        prop_id: {
            type: [Number, String],
            required: true
        },
        prop_text: {
            type: String,
            required: true
        },        
        dependentid: {
            type: String,
            required: false,
            default: ''
        },
        options: {
            type: Object,
            required: true,
        },
        initial_selection: {
            type: Object,
            required: false,
        },  
    },
    data() {
        return {
            imageBaseUri: '',
        }
    },
    mounted() {        
        let vm = this;
        let select = $(this.$refs['select2-vue']);
        select.select2({
            placeholder: vm.placeholder,
            minimumInputLength: vm.minimum_Input_Length,           
            dropdownAutoWidth: true,
            width: 'auto',
            allowClear: vm.allow_clear,
            initSelection: function (element, callback) {
                if (vm.prop_id == 0 || vm.prop_id == '') {                   
                    callback({ id: '', text: '' });
                    return;
                }
                let data = [{ id: vm.prop_id, text: vm.prop_text }];
                callback(data[0]);
                $(select).on('change', function () {
                    vm.$emit('update:model-value', vm.modelValue);                    
                    vm.$emit('child-event-item-id', vm.prop_id);
                    vm.$emit('child-event-item-text', vm.prop_text);
                });  
            },
            ajax: {
                url: this.url,
                dataType: 'json',
                delay: 250,
                data(params) {
                    return {
                        q: params.term,
                        page: params.page,
                    };
                },
                processResults(data, params) {
                    var page = params.page || 1;  
                    return {
                        results: $.map(data.items, function (item) {                           
                            return {
                                id: item.id,
                                text: item.text,                               
                                imageUrl: item.first_picture_url,
                                partNumber: item.manufacturerpartnumber,
                            };
                        }),
                        pagination: {
                            more: (page * data.items_per_page) < data.total_count                            
                        }
                    };
                },
                cache: false,
            },
            templateResult: this.formatState
        })
            .on('select2:select', function (e) {
                vm.$emit('update:model-value', e.params.data.id);                
                vm.$emit('child-event-item-id', e.params.data.id);
                vm.$emit('child-event-item-text', e.params.data.text);
                vm.$emit('child-event', e.params.data.id);
                const message = 'Hello from component ' + vm.dependentid;
                vm.$emit('child-event-fill-dependent-control', { componentKey: vm.dependentid, message });
            })
            .on('select2:clear', function (e) {              
                vm.$emit('child-event-clear');
            });
    },
    methods: {       
        formatState(option){
            if (!option.id) {
                return option.text;
            }            
            var partNumber = option.partNumber ? '<td>' + option.partNumber + '</td>' : '';
            var imageUrl = option.imageUrl ? '<td><img src="/media/' + option.imageUrl + '" style="width:50px;height:50px"/></td>' : '';        
            var $option = $(
                '<table ><tr>' + imageUrl + partNumber + '<td>' + option.text + '</td></tr></table>'
            );
            return $option;
        }
    },
    watch: {
        modelValue: function (value) {
            // update value
            $(this.$refs['select2-vue'])
                .val(value)
                .trigger("change");
        },
        options: function (options) {
            if(options.id == 0 || options.id == '') return;           
            let data = [{ id: options.id, text: options.text }];           
            const option = new Option(data[0].text, data[0].id, true, true);
            $(this.$refs['select2-vue']).append(option);
            $(this.$refs['select2-vue']).trigger('change');
        }
    },
    destroyed() {
        $(this.$refs['select2-vue']).off().select2('destroy');
    },
}
```
### Customized vue component used in this project - [Tiny Calculator](/staticfile/component/tiny_cal/tiny_cal.js)
```javascript
export default {
  template: `<div>
                    <input type="text" :value="modelValue" :tabindex="tab_index" @input="$emit('update:modelValue', $event.target.value)" :disabled="disabled"
                    @keyup="handleKeyup" @keydown="handleKeydown" v-on:blur="handleOnBlur" class="form-control text-right" ref="tiny-cal"  />
                    <div v-show="showPopover" style="position: absolute; background-color: white; border: 1px solid gray; padding: 10px">
                        <textarea ref="tinyInput" v-model="inputCal" rows="3" @keydown.enter="performCalculation" @keydown.tab="performCalculation"
                            @keydown.esc="cancelOperation"></textarea>
                    </div>
                </div>`,
  props: {
    modelValue: {
      type: [String, Number],
      required: true,
    },
    id: {
      type: String,
      required: false,
    },
    name: {
      type: String,
      required: false,
    },
    tab_index: {
      type: [String, Number],
      required: false,
    },
    disabled: {
      type: Boolean,
      required: false,
    },
  },
  data() {
    return {
      amount_returned: 0,
      inputCal: "",
      showPopover: false,
    };
  },
  mounted: function () {
    let vm = this;
    vm.amount_returned = this.modelValue;
    let textInput = $(vm.$refs["tiny-cal"]);
    // set textInput value
    textInput.val(vm.amount_returned);
    // assign id to textInput
    textInput.attr("id", vm.id);
    // assign name to textInput
    textInput.attr("name", vm.name);
  },
  watch: {
    modelValue: function (val) { },
  },
  methods: {
    handleOnBlur(event) {
      // If event.target.value is not a valid number, set it to 0
      let newValue = event.target.value;
      if (!newValue) {
        newValue = 0.0;
      }

      if (isNaN(newValue)) {
        if (newValue.includes(",")) {
          let _value = newValue.replace(/,/g, "");
          if (parseFloat(_value) > 0) {
            newValue = event.target.value;
          } else {
            newValue = 0.0;
          }
        } else {
          newValue = 0.0;
        }
      }

      let hasInvalidChars = /[^0-9.,]/.test(newValue);
      if (hasInvalidChars) {        
        newValue = 0.0;
      }

      if (newValue.toString().includes(",")) {
        newValue = parseFloat(newValue.replace(/,/g, ""));
      }      
      const formattedValue = parseFloat(newValue).toLocaleString("en-US", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      });     
      // Emit the updated value to the parent component
      this.$emit("update:modelValue", formattedValue);
    },
    handleKeydown(event) {
      // disable input of non-numeric characters, except for the following keys
      // +, -, *, /, ., comma, backspace, delete, tab, enter, escape
      const key = event.key;
      const allowedKeys = [
        "Backspace",
        "Delete",
        "Tab",
        "Enter",
        "Escape",
        "+",
        "-",
        "*",
        "/",
        ",",
        ".",
        "0",
        "1",
        "2",
        "3",
        "4",
        "5",
        "6",
        "7",
        "8",
        "9",
      ];

      if (!allowedKeys.includes(event.key)) {
        event.preventDefault();
      }
    },
    handleKeyup(event) {
      let textInput = $(this.$refs["tiny-cal"]);
      let newValue = event.target.value;
      const key = event.key;
      if (["-", "+", "/", "*"].includes(key)) {
        //exract the number from amount and ignore the operator
        const lastChar = newValue[newValue.length - 1];
        if (["-", "+", "/", "*"].includes(lastChar)) {
          textInput.val(newValue.slice(0, -1));
        }
        const firstChar = newValue[0];
        if (["-", "+", "/", "*"].includes(firstChar)) {
          textInput.val(newValue.slice(1));
        }
        if (
          newValue == "" ||
          newValue == null ||
          newValue == undefined ||
          newValue == "*" ||
          newValue == "/" ||
          newValue == "+" ||
          newValue == "-"
        ) {         
          textInput.val("0.00");
        }
        this.$emit("update:modelValue", textInput.val());
        this.inputCal = textInput.val() + "\n" + key + "\n";
        this.showPopover = true;
        this.$nextTick(() => {
          this.$refs.tinyInput.focus();
        });
      }
    },
    performCalculation() {
      const lines = this.inputCal.split("\n");    
      let textInput = $(this.$refs["tiny-cal"]);      
      if (lines.length === 3) {
        let rawNum1 = lines[0];
        const operator = lines[1];
        if (rawNum1.includes(",")) {
          rawNum1 = rawNum1.replace(/,/g, "");
        }
        const num1 = parseFloat(rawNum1);      
        const num2 = parseFloat(lines[2]);      
        let result;
        // latest addition, to check if num1 or num2 is NaN or return 0 instead of NaN
        if (isNaN(num1) || isNaN(num2)) {         
          this.showPopover = false;
          return 0.0;
        }
        // latest addition ends
        switch (operator) {
          case "-":
            result = num1 - num2;
            break;
          case "+":
            result = num1 + num2;
            break;
          case "/":
            result = num1 / num2;
            break;
          case "*":
            result = num1 * num2;
            break;
          default:
            result = "";
            break;
        }       
        const formattedResult = result.toLocaleString("en-US", {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        });      
        textInput.val(formattedResult);
        this.showPopover = false;
        this.$emit("update:modelValue", formattedResult);       
      }
    },
    cancelOperation() {
      this.inputCal = "";
      this.showPopover = false;
    },
  },
};
```
### Data Flow Patterns
#### 1. Django to Vue Data Flow
Pass initial data from Django to Vue:

```html
Refer above html snippet example for details...
```
#### 2. Vue to Django Communication
Use Axios for API calls:

```javascript
Refer above javascript example for details...
```
#### 3. Debugging Vue Components
```javascript

// A custom debugging provision is available on the page.
// By enabling the boolean property `show_selected_ids`, key data properties can be displayed directly on the page.
// This allows real-time inspection of values without needing to open the Vue DevTools or browser console.
// It will be limited to the properties defined in appname_debug_data.html template tag.

// Enable Vue devtools in development
Vue.config.devtools = true;

// Debug template
<div v-if="debug_mode">
    <pre>{{ JSON.stringify(formData, null, 2) }}</pre>
</div>
```
### Styling Guidelines
#### 1. CSS Organization
```
staticfile/
├── component/css/          # Shared component styles
│   ├── common.css         # Common utilities
│   └── grid_action_buttons.css
├── {app_name}/css/        # App-specific styles
│   └── {feature}.css
└── themes/smartadmin/     # Theme styles (don't modify)
```
#### 2. CSS Best Practices
```css
/* Use BEM methodology for custom classes */
.sales-return__form {
    padding: 1rem;
}

.sales-return__form-group {
    margin-bottom: 1rem;
}

.sales-return__form-group--invalid {
    border-color: #dc3545;
}

/* Use SmartAdmin classes when possible */
.custom-width {
    width: 200px;
}

.loading-spinner-center {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
}
```
### Development Workflow
#### 1. Creating a New Feature
1. Create Django template extending base template
2. Create Vue component in appropriate static directory
3. Create CSS file for styling
4. Import and register reusable components
5. Implement data flow and event handling
#### 2. Testing Components
```javascript
// Add validation methods
methods: {
    validateForm() {        
    }
}
```
#### 3. Loading States
```html
<!-- Loading spinner -->
<div class="sk-circle sk-center loading-spinner-center" v-if="loading">
    <div class="sk-circle-dot"></div>
    <!-- ... more dots ... -->
</div>

<!-- Content with blur effect -->
<div class="panel-content" :class="{ 'blur-when-loading': loading }">
    <!-- Content -->
</div>
```
### Performance Considerations

### 1. Component Loading
- Components are loaded as ES6 modules (no bundling)
- Use dynamic imports for large components when needed
- Keep component files focused and small

### 2. Data Management
- Avoid deep reactive objects when possible
- Use computed properties for derived data
- Implement proper loading states

### 3. DOM Manipulation
- Use Vue's reactivity instead of direct DOM manipulation
- Use `v-show` vs `v-if` appropriately
- Implement proper cleanup in component lifecycle

This architecture provides a powerful combination of Django's backend capabilities with Vue.js interactivity while maintaining a simple development workflow without complex build processes.
