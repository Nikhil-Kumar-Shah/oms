# Advanced Form & Transformation Workflow
**Paradox Sports Operations Management System (OMS)**

## 1. Architectural Definition

Forms in Paradox Sports OMS are structured data-entry and workflow mechanisms designed to capture operational requests and transform validated submissions into native OMS records.

> [!NOTE]
> Forms are NOT external survey clones or document stores.
> - Form schemas enforce strongly typed field definitions and validation.
> - Form publishing is version-controlled and immutable once published.
> - Approved submissions can atomically transform into supported native OMS entities (`TASK`, `EVENT`, `REQUIREMENT`, `ISSUE`).
> - External datasets (large participant spreadsheets, high-resolution media) are stored as external references, not duplicated into PostgreSQL core tables.

---

## 2. Form Schema & Field Types

A Form Version (`form_versions` table) defines a JSON schema of fields:

| Field Type | Supported Properties & Validation |
| :--- | :--- |
| `TEXT` | Single-line string, `min_length`, `max_length`, regex pattern |
| `TEXTAREA` | Multi-line text, `max_length` |
| `NUMBER` | Integer or float, `min_value`, `max_value` |
| `DATE` | ISO 8601 Date (`YYYY-MM-DD`) |
| `TIME` | ISO 8601 Time (`HH:MM:SS`) |
| `DATETIME` | ISO 8601 DateTime with timezone |
| `SELECT` | Single choice from fixed `options` array |
| `MULTI_SELECT` | Multiple choices from fixed `options` array |
| `CHECKBOX` | Boolean (`True` / `False`) |
| `FILE_URL` | Validated URL reference to external document/asset |

---

## 3. Form Versioning & Publishing Workflow

```
   ┌───────────┐  publish_version   ┌───────────────────┐  archive_form  ┌──────────┐
   │ DRAFT (v1)│ ─────────────────► │ PUBLISHED (v1.0)  │ ─────────────► │ ARCHIVED │
   └───────────┘                    └─────────┬─────────┘                └──────────┘
                                              │ create_new_draft
                                              ▼
                                    ┌───────────────────┐
                                    │    DRAFT (v2)     │
                                    └───────────────────┘
```

1. **Drafting**: Coordinator or Admin creates form definition with fields in `DRAFT` status.
2. **Publishing**: `POST /api/v1/forms/{id}/versions/{version_id}/publish` locks the schema and assigns active version number (e.g. `v1.0`). Schema becomes immutable.
3. **Submissions Active**: Authenticated users in the target audience can submit responses against the active published version.
4. **Iterative Updates**: Modifying a published form creates a new draft version (`v2`) without altering historical submissions.

---

## 4. Submission Validation & Review Workflow

1. **Submission**: User submits response JSON payload (`POST /api/v1/forms/{id}/submissions`).
2. **Server-Side Validation**: Service validates that all `required` fields exist, types match schema specifications, and constraints (ranges, regex) are satisfied.
3. **Status**: Submission initializes to `SUBMITTED`.
4. **Supervisor Review**: Form reviewer inspects submission (`GET /api/v1/form-submissions/{id}`).
5. **Review Outcome**:
   - `APPROVED`: Response accepted. Triggers optional native OMS entity transformation.
   - `REJECTED`: Response declined with mandatory reviewer remarks.
   - `RETURNED`: Response returned to applicant for corrections.

---

## 5. Native OMS Entity Transformation Rules

When a Form Submission is `APPROVED`, the service can automatically transform the payload into a native OMS record based on the form's `transformation_type`:

| Target Entity | Source Form Fields & Mapping Logic | Resulting Native Record |
| :--- | :--- | :--- |
| `TASK` | `task_title`, `task_desc`, `priority`, `vertical_id`, `deadline` | Creates row in `tasks` and assigns to target vertical |
| `EVENT` | `event_name`, `planned_date`, `location`, `event_type` | Creates row in `events` and initializes 8 readiness checkpoints |
| `REQUIREMENT` | `title`, `description`, `target_vertical_id`, `priority` | Creates row in `requirements` and routes to target vertical |
| `ISSUE` | `issue_title`, `description`, `sensitivity`, `priority` | Creates row in `issues` register |

The generated entity ID is saved in the submission's `transformed_resource_id` field for bidirectional traceability.
