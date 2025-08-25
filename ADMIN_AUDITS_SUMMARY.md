# Admin Interface for Audits - Summary

## ✅ Implemented Features

### 1. **Automatic Audit Creation**
When a new project is created:
- **Lighthouse Audit**: Automatically created for the project homepage only
- **OnPage Audit**: Automatically created with 10,000 page crawl limit

### 2. **Admin Interface Integration**

#### Project Admin (`/admin/project/project/`)
- **List View**: Shows audit status badges for each project
  - 🔍 Lighthouse badge (blue if audited, gray if pending, red if missing)
  - 📊 OnPage badge (green if audited, gray if pending, red if missing)

- **Detail View**: Includes two inline sections:
  1. **Lighthouse Audits Inline**
     - Shows page URL, last audit date, latest scores (Performance, SEO, Accessibility)
     - Direct link to view audit history
     - Enable/disable audit option
  
  2. **OnPage Audits Inline**
     - Shows last audit date, max pages to crawl (10,000), total issues
     - Issues summary with breakdown (broken links, missing titles, etc.)
     - Direct link to view audit history
     - Enable/disable audit option

- **Audit Summary Section**: Detailed overview showing:
  - Total audits run for each type
  - Latest audit results and scores
  - Direct links to full audit histories

### 3. **Standalone Admin Pages**

#### Lighthouse Audits (`/admin/audits/auditpage/`)
- Full management of Lighthouse audits
- View all audit pages across projects
- Score badges for quick overview
- Run manual audits
- View detailed history

#### OnPage Audits (`/admin/onpageaudit/onpageaudit/`)
- Full management of OnPage/Screaming Frog audits
- Issue counts and summaries
- Rate limiting status
- Manual audit triggers
- Detailed history with comparison badges

### 4. **Configuration Details**

- **Lighthouse**: Audits only the homepage (`https://{project.domain}`)
- **OnPage/Screaming Frog**: 
  - Max crawl limit: 10,000 pages
  - Configured in `onpageaudit/tasks.py:266`
  - Rate limited to prevent overuse

### 5. **Signal Handlers**
Located in `project/signals.py`:
- Automatically triggers both audit types when a project is created
- Works for projects created via:
  - Admin interface
  - API
  - Django shell
  - Any other method

## 📋 How to Use

1. **Create a new project** in the admin at `/admin/project/project/add/`
2. Both audits will be **automatically queued** via Celery
3. Navigate to the project detail page to see:
   - Inline audit summaries
   - Current status
   - Links to full histories
4. Use the **View History** buttons to see detailed audit results
5. Audits can be **manually triggered** from their respective admin pages

## 🔧 Technical Details

- **Files Modified**:
  - `project/admin.py`: Added inline admins and audit status display
  - `onpageaudit/tasks.py`: Set 10,000 page limit for new projects
  - `project/signals.py`: Already configured to trigger audits

- **Models Used**:
  - `AuditPage`: Lighthouse audit configuration
  - `AuditHistory`: Lighthouse audit results
  - `OnPageAudit`: Screaming Frog configuration
  - `OnPageAuditHistory`: Screaming Frog results

## 🎯 Result

The admin interface now provides a comprehensive view of all audits directly within the Project admin page, making it easy to:
- Monitor audit status at a glance
- View latest results without leaving the project page
- Access detailed histories when needed
- Manage audit configurations per project

All new projects automatically get both audit types configured with the specified limits!