import { useEffect, useRef, useState } from 'react'
import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useNavigate, useParams } from 'react-router-dom'
import { referenceService } from '../../services/referenceService'
import { exceptionService } from '../../services/exceptionService'

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

const EMPTY_DEFAULTS = {
  business_unit: '', exception_type: '', risk_issue: '',
  asset_type: '', asset_purpose: '', data_classification: '',
  data_components: [], internet_exposure: '',
  number_of_assets: '', short_description: '', reason_for_exception: '',
  compensatory_controls: '', exception_end_date: '',
  assigned_approver: '', risk_owner: '',
}

function getSavedDraft() {
  if (typeof window === 'undefined') return null
  const raw = window.localStorage.getItem(DRAFT_STORAGE_KEY)
  if (!raw) return null
  try { return JSON.parse(raw) } catch { return null }
}

function normalizeSavedDraft(draft) {
  if (!draft || typeof draft !== 'object') return draft
  const value = draft.exception_end_date
  if (value && value.includes('/')) {
    return { ...draft, exception_end_date: '' }
  }
  return draft
}

function RequiredMark() {
  return <span className="ml-1 text-red-600">*</span>
}

function parseIsoDate(value) {
  if (!value || typeof value !== 'string') return null
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return null
  return parsed
}

function isFutureCalendarDate(value) {
  const parsed = parseIsoDate(value)
  if (!parsed) return false
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0, 0)
  return parsed.getTime() > today.getTime()
}

function toDateInputValue(isoString) {
  if (!isoString) return ''
  const d = new Date(isoString)
  if (Number.isNaN(d.getTime())) return ''
  return d.toISOString().slice(0, 10)
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
  exception_end_date: 'Select a future date from the calendar.',
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
    .refine((value) => parseIsoDate(value) !== null, 'Invalid date format')
    .refine((value) => isFutureCalendarDate(value), 'Date must be in the future'),
  assigned_approver:    z.string().min(1, 'Required'),
  risk_owner:           z.string().min(1, 'Required'),
})

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

// ── Inner form — always mounted with correct defaultValues, never needs form.reset ──

function ExceptionFormInner({ navigate, isEditMode, exceptionId, exceptionTitle, defaultValues, refData }) {
  const [submitError, setSubmitError] = useState(null)
  const [loadingApprover, setLoadingApprover] = useState(false)

  const form = useForm({
    resolver: zodResolver(schema),
    defaultValues,
  })

  // Skip first auto-populate run in edit mode; values are already correct from defaultValues.
  const skipFirst = useRef(isEditMode)

  const buWatched = form.watch('business_unit')
  const etWatched = form.watch('exception_type')

  useEffect(() => {
    if (skipFirst.current) {
      skipFirst.current = false
      return
    }
    if (!buWatched && !etWatched) return

    setLoadingApprover(true)
    referenceService.getAssignmentDefaults(buWatched, etWatched)
      .then(response => {
        if (response.data.assigned_approver_id) {
          form.setValue('assigned_approver', String(response.data.assigned_approver_id))
        }
        if (response.data.risk_owner_id) {
          form.setValue('risk_owner', String(response.data.risk_owner_id))
        }
      })
      .catch(err => console.error('Failed to fetch assignment defaults:', err))
      .finally(() => setLoadingApprover(false))
  }, [buWatched, etWatched])

  // Persist form to localStorage (create mode only)
  useEffect(() => {
    if (isEditMode) return
    const subscription = form.watch((values) => {
      window.localStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(values))
    })
    return () => subscription.unsubscribe()
  }, [form, isEditMode])

  async function onSubmit(values) {
    setSubmitError(null)
    try {
      const parsedEndDate = parseIsoDate(values.exception_end_date)
      if (!parsedEndDate) {
        form.setError('exception_end_date', { message: 'Invalid date format' })
        setSubmitError('Please fix the errors above.')
        return
      }

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
        exception_end_date:  parsedEndDate.toISOString(),
      }

      if (isEditMode) {
        await exceptionService.updateException(exceptionId, payload)
        navigate('/', { state: { message: `Draft #${exceptionId} saved successfully.` } })
      } else {
        await exceptionService.createException(payload)
        window.localStorage.removeItem(DRAFT_STORAGE_KEY)
        navigate('/', { state: { message: 'Exception request created successfully.' } })
      }
    } catch (err) {
      const data = err.response?.data
      if (data && typeof data === 'object') {
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

  const { business_units, exception_types, risk_issues, asset_types, asset_purposes,
          data_classifications, data_components, internet_exposures, users, approvers, risk_owners } = refData

  const approverOptions = approvers?.length ? approvers : users
  const riskOwnerOptions = risk_owners?.length ? risk_owners : users
  const formatUserOption = (user) => {
    const name = user.full_name || user.username
    return user.email ? `${name} (${user.email})` : name
  }

  const isSubmitting = form.formState.isSubmitting
  const errorEntries = Object.entries(form.formState.errors).map(([fieldName, fieldError]) => ({
    fieldName,
    label: FIELD_LABELS[fieldName] ?? fieldName,
    message: fieldError?.message ?? 'Invalid value',
    fix: FIELD_FIX_HELP[fieldName] ?? 'Review and correct this field.',
  }))
  const showErrorSummary = form.formState.submitCount > 0 && errorEntries.length > 0

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="bg-white border-b border-slate-200 px-6 py-4">
        <div className="max-w-4xl mx-auto flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate('/')}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-xl font-semibold text-slate-900">
              {isEditMode ? 'Edit Exception Request' : 'New Exception Request'}
            </h1>
            <p className="text-sm text-slate-500">
              {isEditMode
                ? `${exceptionTitle} — edit fields below, then submit to restart the approval process`
                : 'Submit a formal request for a policy exception'}
            </p>
          </div>
        </div>
      </div>

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
                        className={fieldState.error ? 'border-red-500 ring-1 ring-red-500' : ''}
                        {...field}
                      />
                    </FormControl>
                    <FormDescription>Select a future date from the calendar</FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
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
                                    : field.value.filter(i => i !== dc.id)
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

            <FormSection
              title="Assignment"
              description="Assign the BU CIO who must approve this exception and the risk owner responsible for its oversight."
            >
              <SelectField
                control={form.control} name="assigned_approver" label="Assigned Approver (BU CIO)"
                options={approverOptions} placeholder={loadingApprover ? 'Loading…' : 'Auto-assigned on BU selection'}
                getOptionLabel={formatUserOption} required
                disabled={loadingApprover || (!isEditMode && !!form.watch('assigned_approver'))}
              />
              <SelectField
                control={form.control} name="risk_owner" label="Risk Owner"
                options={riskOwnerOptions} placeholder={loadingApprover ? 'Loading…' : 'Auto-assigned on Exception Type selection'}
                getOptionLabel={formatUserOption} required
                disabled={loadingApprover || (!isEditMode && !!form.watch('risk_owner'))}
              />
            </FormSection>

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
                {isSubmitting
                  ? (isEditMode ? 'Saving…' : 'Submitting…')
                  : (isEditMode ? 'Save Changes' : 'Create Exception Request')}
              </Button>
            </div>

          </form>
        </Form>
      </div>
    </div>
  )
}

// ── Outer loader — fetches all data before rendering the form ──

export default function CreateExceptionPage() {
  const navigate = useNavigate()
  const { id } = useParams()
  const isEditMode = !!id

  const [loadState, setLoadState] = useState({ loading: true, error: null, refData: null, excData: null })

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const [refRes, excRes] = await Promise.all([
          referenceService.getReferenceData(),
          isEditMode ? exceptionService.getExceptionDetails(id) : Promise.resolve(null),
        ])
        if (!cancelled) {
          setLoadState({ loading: false, error: null, refData: refRes.data, excData: excRes?.data ?? null })
        }
      } catch {
        if (!cancelled) {
          setLoadState(s => ({ ...s, loading: false, error: 'Failed to load. Please refresh and try again.' }))
        }
      }
    }
    load()
    return () => { cancelled = true }
  }, [isEditMode, id])

  if (loadState.loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
      </div>
    )
  }

  if (loadState.error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4">
        <p className="text-red-600">{loadState.error}</p>
        <Button variant="outline" onClick={() => window.location.reload()}>Retry</Button>
      </div>
    )
  }

  let defaultValues
  if (isEditMode && loadState.excData) {
    const exc = loadState.excData
    defaultValues = {
      business_unit:         String(exc.business_unit),
      exception_type:        String(exc.exception_type),
      risk_issue:            String(exc.risk_issue),
      asset_type:            String(exc.asset_type),
      asset_purpose:         String(exc.asset_purpose),
      data_classification:   String(exc.data_classification),
      internet_exposure:     String(exc.internet_exposure),
      number_of_assets:      exc.number_of_assets,
      short_description:     exc.short_description ?? '',
      reason_for_exception:  exc.reason_for_exception ?? '',
      compensatory_controls: exc.compensatory_controls ?? '',
      exception_end_date:    toDateInputValue(exc.exception_end_date),
      assigned_approver:     String(exc.assigned_approver),
      risk_owner:            String(exc.risk_owner),
      data_components:       (exc.data_components ?? []).map(Number),
    }
  } else {
    defaultValues = normalizeSavedDraft(getSavedDraft()) ?? EMPTY_DEFAULTS
  }

  return (
    <ExceptionFormInner
      key={isEditMode ? `edit-${id}` : 'create'}
      navigate={navigate}
      isEditMode={isEditMode}
      exceptionId={id}
      exceptionTitle={isEditMode && loadState.excData ? `Draft #${loadState.excData.id}` : ''}
      defaultValues={defaultValues}
      refData={loadState.refData}
    />
  )
}
