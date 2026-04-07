import { useEffect, useState } from 'react'
import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useNavigate } from 'react-router-dom'
import { api } from './api'

import {
  Form, FormField, FormItem, FormLabel, FormControl, FormDescription, FormMessage,
} from '@/components/ui/form'
import { Button }   from '@/components/ui/button'
import { Input }    from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label }    from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import {
  Card, CardContent, CardHeader, CardTitle, CardDescription,
} from '@/components/ui/card'
import { ArrowLeft, Loader2 } from 'lucide-react'

const DRAFT_STORAGE_KEY = 'create-exception-form-draft'

function getSavedDraft() {
  if (typeof window === 'undefined') {
    return null
  }

  const raw = window.localStorage.getItem(DRAFT_STORAGE_KEY)
  if (!raw) {
    return null
  }

  try {
    return JSON.parse(raw)
  } catch {
    return null
  }
}

function RequiredMark() {
  return <span className="ml-1 text-red-600">*</span>
}

function parseYyyyMmDdToDate(value) {
  if (!value || typeof value !== 'string') return null
  const match = value.trim().match(/^(\d{4})-(\d{2})-(\d{2})$/)
  if (!match) return null

  const year = Number(match[1])
  const month = Number(match[2])
  const day = Number(match[3])
  const parsed = new Date(year, month - 1, day, 0, 0, 0, 0)

  if (
    Number.isNaN(parsed.getTime()) ||
    parsed.getFullYear() !== year ||
    parsed.getMonth() !== month - 1 ||
    parsed.getDate() !== day
  ) {
    return null
  }

  return parsed
}

function parseDdMmYyyyToDate(value) {
  if (!value || typeof value !== 'string') return null
  const match = value.trim().match(/^(\d{2})\/(\d{2})\/(\d{4})$/)
  if (!match) return null

  const day = Number(match[1])
  const month = Number(match[2])
  const year = Number(match[3])
  const parsed = new Date(year, month - 1, day, 0, 0, 0, 0)

  if (
    Number.isNaN(parsed.getTime()) ||
    parsed.getFullYear() !== year ||
    parsed.getMonth() !== month - 1 ||
    parsed.getDate() !== day
  ) {
    return null
  }

  return parsed
}

function parseExceptionEndDate(value) {
  return parseYyyyMmDdToDate(value) || parseDdMmYyyyToDate(value)
}

function isFutureCalendarDate(value) {
  const parsed = parseExceptionEndDate(value)
  if (!parsed) return false

  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0, 0)
  return parsed.getTime() > today.getTime()
}

function toYyyyMmDd(value) {
  const parsed = parseExceptionEndDate(value)
  if (parsed) {
    return `${parsed.getFullYear()}-${String(parsed.getMonth() + 1).padStart(2, '0')}-${String(parsed.getDate()).padStart(2, '0')}`
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function getTomorrowDateString() {
  const today = new Date()
  const tomorrow = new Date(today.getFullYear(), today.getMonth(), today.getDate() + 1, 0, 0, 0, 0)
  return `${tomorrow.getFullYear()}-${String(tomorrow.getMonth() + 1).padStart(2, '0')}-${String(tomorrow.getDate()).padStart(2, '0')}`
}

const FIELD_LABELS = {
  business_unit: 'Business Unit',
  exception_type: 'Exception Type',
  risk_issue: 'Risk / Issue',
  exception_end_date: 'Exception End Date',
  short_description: 'Short Description',
  reason_for_exception: 'Reason for Exception',
  asset_type: 'Asset Type',
  asset_purpose: 'Asset Purpose',
  data_classification: 'Data Classification',
  internet_exposure: 'Internet Exposure',
  number_of_assets: 'Number of Assets',
  data_components: 'Data Components',
  assigned_approver: 'Assigned Approver (BU CIO)',
  risk_owner: 'Risk Owner',
}

const FIELD_FIX_HELP = {
  business_unit: 'Select a business unit from the dropdown.',
  exception_type: 'Select an exception type.',
  risk_issue: 'Select the related risk/issue.',
  exception_end_date: 'Choose a future date using the calendar.',
  short_description: 'Enter at least 10 characters.',
  reason_for_exception: 'Enter at least 20 characters explaining the reason.',
  asset_type: 'Select an asset type.',
  asset_purpose: 'Select an asset purpose.',
  data_classification: 'Select a data classification.',
  internet_exposure: 'Select an internet exposure level.',
  number_of_assets: 'Enter a whole number greater than or equal to 1.',
  data_components: 'Select at least one data component checkbox.',
  assigned_approver: 'Select a BU CIO/approver from the list.',
  risk_owner: 'Select a risk owner from the list.',
}

// ─── Zod validation schema ────────────────────────────────────────────────────
const schema = z.object({
  business_unit:        z.string().min(1, 'Required'),
  exception_type:       z.string().min(1, 'Required'),
  risk_issue:           z.string().min(1, 'Required'),
  asset_type:           z.string().min(1, 'Required'),
  asset_purpose:        z.string().min(1, 'Required'),
  data_classification:  z.string().min(1, 'Required'),
  data_components:      z.array(z.number()).min(1, 'Select at least one data component'),
  internet_exposure:    z.string().min(1, 'Required'),
  number_of_assets:     z.coerce.number().int().min(1, 'Must be at least 1'),
  short_description:    z.string().min(10, 'Minimum 10 characters'),
  reason_for_exception: z.string().min(20, 'Minimum 20 characters'),
  compensatory_controls:z.string().optional(),
  exception_end_date:   z
    .string()
    .min(1, 'Required')
    .refine((value) => parseExceptionEndDate(value) !== null, 'Use the date picker to select a valid date')
    .refine((value) => isFutureCalendarDate(value), 'Date must be in the future'),
  assigned_approver:    z.string().min(1, 'Required'),
  risk_owner:           z.string().min(1, 'Required'),
})

// ─── Section wrapper ──────────────────────────────────────────────────────────
function FormSection({ title, description, children }) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle>{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent>
        <div className="grid gap-5 sm:grid-cols-2">
          {children}
        </div>
      </CardContent>
    </Card>
  )
}

function normalizeSavedDraft(draft) {
  if (!draft || typeof draft !== 'object') return draft
  const value = draft.exception_end_date
  if (!value || typeof value !== 'string') return draft
  if (/^\d{4}-\d{2}-\d{2}$/.test(value.trim())) return draft

  const normalized = toYyyyMmDd(value)
  if (!normalized) return draft

  return {
    ...draft,
    exception_end_date: normalized,
  }
}

// ─── Reusable Select field ────────────────────────────────────────────────────
function SelectField({ control, name, label, description, placeholder, options, valueKey = 'id', labelKey, getOptionLabel, required = false, disabled = false }) {
  return (
    <FormField
      control={control}
      name={name}
      render={({ field, fieldState }) => (
        <FormItem>
          <FormLabel className={fieldState.error ? 'text-red-600' : ''}>{label}{required && <RequiredMark />}</FormLabel>
          <FormControl>
            <Select onValueChange={field.onChange} value={field.value} disabled={disabled}>
              <SelectTrigger className={`w-full ${fieldState.error ? 'border-red-500 ring-1 ring-red-500' : ''}`}>
                <SelectValue placeholder={placeholder ?? `Select ${label.toLowerCase()}`} />
              </SelectTrigger>
              <SelectContent className="max-h-60 overflow-y-auto">
                {options.map(opt => (
                  <SelectItem key={opt[valueKey]} value={String(opt[valueKey])}>
                    {getOptionLabel
                      ? getOptionLabel(opt)
                      : (labelKey ? opt[labelKey] : opt.name ?? opt.label ?? opt.title ?? opt.level)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FormControl>
          {description && <FormDescription>{description}</FormDescription>}
          <FormMessage />
        </FormItem>
      )}
    />
  )
}

// ─── Main page component ──────────────────────────────────────────────────────
export default function CreateExceptionPage() {
  const navigate = useNavigate()
  const [refData, setRefData] = useState(null)
  const [loadingRef, setLoadingRef] = useState(true)
  const [refError, setRefError]     = useState(null)
  const [submitError, setSubmitError] = useState(null)
  const [loadingApprover, setLoadingApprover] = useState(false)

  const savedDraft = normalizeSavedDraft(getSavedDraft())

  const form = useForm({
    resolver: zodResolver(schema),
    defaultValues: savedDraft ?? {
      business_unit: '', exception_type: '', risk_issue: '',
      asset_type: '', asset_purpose: '', data_classification: '',
      data_components: [], internet_exposure: '',
      number_of_assets: '', short_description: '', reason_for_exception: '',
      compensatory_controls: '', exception_end_date: '',
      assigned_approver: '', risk_owner: '',
    },
  })

  // Load reference data on mount
  useEffect(() => {
    api.get('/api/reference/')
      .then(r => setRefData(r.data))
      .catch(() => setRefError('Failed to load form options. Please refresh.'))
      .finally(() => setLoadingRef(false))
  }, [])

  // Auto-populate assigned_approver when business_unit changes
  useEffect(() => {
    const businessUnitId = form.getValues('business_unit')
    if (!businessUnitId) {
      form.setValue('assigned_approver', '')
      setLoadingApprover(false)
      return
    }

    setLoadingApprover(true)
    api.get(`/api/exceptions/get_approver_by_bu/?business_unit_id=${businessUnitId}`)
      .then(response => {
        form.setValue('assigned_approver', String(response.data.assigned_approver_id))
      })
      .catch(err => {
        console.error('Failed to fetch approver:', err)
        form.setValue('assigned_approver', '')
      })
      .finally(() => setLoadingApprover(false))
  }, [form.watch('business_unit')])

  useEffect(() => {
    const subscription = form.watch((values) => {
      window.localStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(values))
    })

    return () => subscription.unsubscribe()
  }, [form])

  async function onSubmit(values) {
    setSubmitError(null)
    try {
      const parsedEndDate = parseExceptionEndDate(values.exception_end_date)
      if (!parsedEndDate) {
        form.setError('exception_end_date', { message: 'Use the date picker to select a valid date' })
        setSubmitError('Please fix the errors above.')
        return
      }

      // Convert string IDs from Select back to numbers for the API
      const payload = {
        ...values,
        business_unit:       parseInt(values.business_unit),
        exception_type:      parseInt(values.exception_type),
        risk_issue:          parseInt(values.risk_issue),
        asset_type:          parseInt(values.asset_type),
        asset_purpose:       parseInt(values.asset_purpose),
        data_classification: parseInt(values.data_classification),
        internet_exposure:   parseInt(values.internet_exposure),
        assigned_approver:   parseInt(values.assigned_approver),
        risk_owner:          parseInt(values.risk_owner),
        // data_components is already an array of numbers
        // exception_end_date: DD/MM/YYYY string → ISO
        exception_end_date: parsedEndDate.toISOString(),
      }
      await api.post('/api/exceptions/', payload)
      window.localStorage.removeItem(DRAFT_STORAGE_KEY)
      navigate('/', { state: { message: 'Exception request created successfully.' } })
    } catch (err) {
      const data = err.response?.data
      if (data && typeof data === 'object') {
        // Map backend field errors back into the form
        Object.entries(data).forEach(([field, msgs]) => {
          if (field in form.getValues()) {
            form.setError(field, { message: Array.isArray(msgs) ? msgs[0] : msgs })
          }
        })
        setSubmitError('Please fix the errors above.')
      } else {
        setSubmitError('Submission failed. Please try again.')
      }
    }
  }

  // ── Loading / error states ─────────────────────────────────────────────────
  if (loadingRef) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
      </div>
    )
  }

  if (refError) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4">
        <p className="text-red-600">{refError}</p>
        <Button variant="outline" onClick={() => window.location.reload()}>Retry</Button>
      </div>
    )
  }

  const { business_units, exception_types, risk_issues, asset_types, asset_purposes,
          data_classifications, data_components, internet_exposures, users, approvers, risk_owners } = refData

  const approverOptions = approvers?.length ? approvers : users
  const riskOwnerOptions = risk_owners?.length ? risk_owners : users
  const formatUserOption = (user) => {
    const name = user.full_name || user.username
    return user.email ? `${name} (${user.email})` : name
  }

  const isSubmitting = form.formState.isSubmitting
  const minSelectableEndDate = getTomorrowDateString()
  const errorEntries = Object.entries(form.formState.errors).map(([fieldName, fieldError]) => ({
    fieldName,
    label: FIELD_LABELS[fieldName] ?? fieldName,
    message: fieldError?.message ?? 'Invalid value',
    fix: FIELD_FIX_HELP[fieldName] ?? 'Review and correct this field.',
  }))
  const showErrorSummary = form.formState.submitCount > 0 && errorEntries.length > 0

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <div className="bg-white border-b border-slate-200 px-6 py-4">
        <div className="max-w-4xl mx-auto flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate('/')}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-xl font-semibold text-slate-900">New Exception Request</h1>
            <p className="text-sm text-slate-500">Submit a formal request for a policy exception</p>
          </div>
        </div>
      </div>

      {/* Form body */}
      <div className="max-w-4xl mx-auto px-6 py-8">
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">

            {showErrorSummary && (
              <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                <p className="font-semibold">Please fix the highlighted fields:</p>
                <ul className="mt-2 list-disc pl-5 space-y-1">
                  {errorEntries.map(err => (
                    <li key={err.fieldName}>
                      <span className="font-medium">{err.label}:</span> {String(err.message)}. <span className="font-medium">How to fix:</span> {err.fix}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <p className="text-xs text-slate-500">Fields marked with <span className="text-red-600">*</span> are required.</p>

            {/* ── Section 1: Exception Details ────────────────────────────── */}
            <FormSection
              title="Exception Details"
              description="Identify the business context and describe what policy is being excepted."
            >
              <SelectField
                control={form.control} name="business_unit" label="Business Unit"
                options={business_units} labelKey="name" required
              />
              <SelectField
                control={form.control} name="exception_type" label="Exception Type"
                options={exception_types} labelKey="name" required
              />
              <SelectField
                control={form.control} name="risk_issue" label="Risk / Issue"
                options={risk_issues} labelKey="title" required
              />
              <FormField
                control={form.control} name="exception_end_date"
                render={({ field, fieldState }) => (
                  <FormItem>
                    <FormLabel className={fieldState.error ? 'text-red-600' : ''}>Exception End Date<RequiredMark /></FormLabel>
                    <FormControl>
                      <Input
                        type="date"
                        min={minSelectableEndDate}
                        className={fieldState.error ? 'border-red-500 ring-1 ring-red-500' : ''}
                        {...field}
                      />
                    </FormControl>
                    <FormDescription>Select a future date</FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Full-width textareas */}
              <FormField
                control={form.control} name="short_description"
                render={({ field, fieldState }) => (
                  <FormItem className="sm:col-span-2">
                    <FormLabel className={fieldState.error ? 'text-red-600' : ''}>Short Description<RequiredMark /></FormLabel>
                    <FormControl>
                      <Textarea className={fieldState.error ? 'border-red-500 ring-1 ring-red-500' : ''} placeholder="Briefly describe the exception being requested…" rows={2} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control} name="reason_for_exception"
                render={({ field, fieldState }) => (
                  <FormItem className="sm:col-span-2">
                    <FormLabel className={fieldState.error ? 'text-red-600' : ''}>Reason for Exception<RequiredMark /></FormLabel>
                    <FormControl>
                      <Textarea className={fieldState.error ? 'border-red-500 ring-1 ring-red-500' : ''} placeholder="Explain why this exception is necessary…" rows={3} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control} name="compensatory_controls"
                render={({ field, fieldState }) => (
                  <FormItem className="sm:col-span-2">
                    <FormLabel className={fieldState.error ? 'text-red-600' : ''}>Compensatory Controls <span className="font-normal text-slate-400">(optional)</span></FormLabel>
                    <FormControl>
                      <Textarea className={fieldState.error ? 'border-red-500 ring-1 ring-red-500' : ''} placeholder="Describe any mitigating controls in place…" rows={2} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </FormSection>

            {/* ── Section 2: Risk Assessment ───────────────────────────────── */}
            <FormSection
              title="Risk Assessment"
              description="These fields are used to automatically calculate a risk score for this exception."
            >
              <SelectField
                control={form.control} name="asset_type" label="Asset Type"
                options={asset_types} labelKey="name" required
              />
              <SelectField
                control={form.control} name="asset_purpose" label="Asset Purpose"
                options={asset_purposes} labelKey="name" required
              />
              <SelectField
                control={form.control} name="data_classification" label="Data Classification"
                options={data_classifications} labelKey="level" required
              />
              <SelectField
                control={form.control} name="internet_exposure" label="Internet Exposure"
                options={internet_exposures} labelKey="label" required
              />
              <FormField
                control={form.control} name="number_of_assets"
                render={({ field, fieldState }) => (
                  <FormItem>
                    <FormLabel className={fieldState.error ? 'text-red-600' : ''}>Number of Assets<RequiredMark /></FormLabel>
                    <FormControl>
                      <Input type="number" min={1} className={fieldState.error ? 'border-red-500 ring-1 ring-red-500' : ''} placeholder="e.g. 5" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Data Components — multi-select checkboxes */}
              <Controller
                control={form.control}
                name="data_components"
                render={({ field, fieldState }) => (
                  <div className="sm:col-span-2 space-y-2">
                    <Label className={fieldState.error ? 'text-red-600' : ''}>
                      Data Components <RequiredMark />
                    </Label>
                    <div className={`grid grid-cols-2 sm:grid-cols-3 gap-2 rounded-md border bg-slate-50 p-3 ${fieldState.error ? 'border-red-500 ring-1 ring-red-500' : 'border-slate-200'}`}>
                      {data_components.map(dc => {
                        const checked = field.value.includes(dc.id)
                        return (
                          <label key={dc.id} className="flex items-center gap-2 cursor-pointer select-none text-sm">
                            <Checkbox
                              checked={checked}
                              onCheckedChange={checked => {
                                field.onChange(
                                  checked
                                    ? [...field.value, dc.id]
                                    : field.value.filter(id => id !== dc.id)
                                )
                              }}
                            />
                            {dc.name}
                          </label>
                        )
                      })}
                    </div>
                    {fieldState.error && (
                      <p className="text-xs font-medium text-red-600">{fieldState.error.message}</p>
                    )}
                  </div>
                )}
              />
            </FormSection>

            {/* ── Section 3: Assignment ────────────────────────────────────── */}
            <FormSection
              title="Assignment"
              description="Assign the BU CIO who must approve this exception and the risk owner responsible for its oversight."
            >
              <SelectField
                control={form.control} name="assigned_approver" label="Assigned Approver (BU CIO)"
                options={approverOptions} placeholder="Select approver"
                getOptionLabel={formatUserOption} required
                             disabled={loadingApprover}
              />
              <SelectField
                control={form.control} name="risk_owner" label="Risk Owner"
                options={riskOwnerOptions} placeholder="Select risk owner"
                getOptionLabel={formatUserOption} required
              />
            </FormSection>

            {/* ── Submit area ──────────────────────────────────────────────── */}
            {submitError && (
              <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {submitError}
              </div>
            )}

            <div className="flex items-center justify-end gap-3 pt-2">
              <Button type="button" variant="outline" onClick={() => navigate('/')} disabled={isSubmitting}>
                Cancel
              </Button>
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {isSubmitting ? 'Submitting…' : 'Create Exception Request'}
              </Button>
            </div>

          </form>
        </Form>
      </div>
    </div>
  )
}
