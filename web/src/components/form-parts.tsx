"use client";

import { CircleAlert, CircleCheck, Eye, EyeOff, Loader2, AlertCircle } from "lucide-react";
import {
  cloneElement,
  useId,
  useState,
  type ComponentProps,
  type ReactElement,
  type ReactNode,
} from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { FormState } from "@/lib/auth/actions";
import { cn } from "@/lib/utils";

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function validateEmail(value: string): string | null {
  const trimmed = value.trim();
  if (trimmed === "") return "Email is required";
  if (!EMAIL_REGEX.test(trimmed)) return "Enter a valid email address";
  return null;
}

function strengthLabel(password: string): string | null {
  if (!password) return null;
  if (password.length < 8) return "Very weak";
  const hasLower = /[a-z]/.test(password);
  const hasUpper = /[A-Z]/.test(password);
  const hasDigit = /\d/.test(password);
  const hasSpecial = /[^a-zA-Z0-9\s]/.test(password) || /\s/.test(password);
  const variety = [hasLower, hasUpper, hasDigit, hasSpecial].filter(Boolean).length;
  const words = password.trim().split(/\s+/).length;

  // Long passphrase beats short complexity: 4+ words and 20+ chars is strong by itself.
  if (words >= 4 && password.length >= 20) return "Strong";
  if (password.length >= 20 && variety >= 2) return "Strong";
  if (password.length >= 16 && variety >= 2) return "Strong";
  if (password.length >= 12 && variety >= 3) return "Good";
  if (password.length >= 12 && variety >= 2) return "Good";
  if (password.length >= 10 && variety >= 2) return "Fair";
  if (password.length >= 10) return "Fair";
  if (variety >= 2) return "Weak";
  return "Weak";
}

function strengthColor(label: string | null): string {
  switch (label) {
    case "Very weak":
    case "Weak":
      return "text-destructive";
    case "Fair":
      return "text-warning";
    case "Good":
      return "text-primary";
    case "Strong":
      return "text-success";
    default:
      return "text-muted-foreground";
  }
}

function strengthVariant(label: string | null): "default" | "destructive" | "warning" | "success" {
  switch (label) {
    case "Very weak":
    case "Weak":
      return "destructive";
    case "Fair":
      return "warning";
    case "Good":
      return "default";
    case "Strong":
      return "success";
    default:
      return "default";
  }
}

/** A labelled input with optional password visibility toggle, inline email validation, and strength hint. */
export function Field({
  label,
  name,
  hint,
  type = "text",
  className,
  showStrength,
  error,
  onFocus,
  onBlur,
  onChange,
  ...props
}: ComponentProps<typeof Input> & {
  label: string;
  name: string;
  hint?: ReactNode;
  showStrength?: boolean;
  error?: string;
}) {
  const id = `field-${name}`;
  const isPassword = type === "password";
  const isEmail = type === "email";
  const [showPassword, setShowPassword] = useState(false);
  const [emailError, setEmailError] = useState<string | null>(null);
  const [touched, setTouched] = useState(false);
  const [focused, setFocused] = useState(false);
  const [passwordValue, setPasswordValue] = useState(() =>
    typeof props.defaultValue === "string" ? (props.defaultValue as string) : "",
  );

  const labelStrength = isPassword && showStrength ? strengthLabel(passwordValue) : null;
  const showEmailError = isEmail && touched && !!emailError;
  const hasExternalError = !!error;
  const showError = showEmailError || hasExternalError;
  const errorMessage = hasExternalError ? error : emailError;

  const describedBy =
    [
      showError ? `${id}-error` : null,
      labelStrength ? `${id}-strength` : null,
      hint ? `${id}-hint` : null,
    ]
      .filter(Boolean)
      .join(" ") || undefined;

  const ariaInvalid = showError ? "true" : touched && isEmail ? "false" : undefined;

  const inputBorderClass = cn(
    showError &&
      "border-destructive focus-visible:border-destructive focus-visible:ring-destructive/20",
    focused && !showError && "border-ring focus-visible:ring-ring/50",
    hasExternalError && "bg-destructive/5",
  );

  const updatePasswordStrength = (value: string) => {
    if (isPassword && showStrength) setPasswordValue(value);
  };

  const validateEmailField = (element: HTMLInputElement) => {
    if (!isEmail) return;
    const next = validateEmail(element.value);
    setTouched(true);
    setEmailError(next);
    // Trim whitespace on blur so a pasted " foo@bar.com " doesn't submit with spaces.
    if (element.value !== element.value.trim()) element.value = element.value.trim();
  };

  return (
    <div className={cn("space-y-1.5", className)}>
      <Label htmlFor={id} className="text-sm font-medium transition-colors">
        {label}
      </Label>
      <div className="relative">
        <Input
          {...props}
          id={id}
          name={name}
          type={isPassword ? (showPassword ? "text" : "password") : type}
          aria-describedby={describedBy}
          aria-invalid={ariaInvalid}
          className={cn(
            isPassword ? "pr-10" : undefined,
            inputBorderClass,
            "transition-all duration-200",
          )}
          onFocus={(e) => {
            setFocused(true);
            onFocus?.(e);
          }}
          onBlur={(e) => {
            setFocused(false);
            validateEmailField(e.currentTarget);
            onBlur?.(e as unknown as React.FocusEvent<HTMLInputElement>);
          }}
          onBlurCapture={(e) => validateEmailField(e.currentTarget)}
          onKeyDown={(e) => {
            // Safari/WebKit can move focus before dispatching the delegated
            // blur state update. Validate the same keyboard exit explicitly so
            // keyboard users receive identical feedback across engines.
            if (isEmail && e.key === "Tab") validateEmailField(e.currentTarget);
            props.onKeyDown?.(e);
          }}
          onChange={(e) => {
            const v = e.currentTarget.value;
            if (isEmail && touched) {
              const next = validateEmail(v);
              setEmailError(next);
            }
            updatePasswordStrength(v);
            onChange?.(e as unknown as React.ChangeEvent<HTMLInputElement>);
          }}
          onInput={(e) => updatePasswordStrength(e.currentTarget.value)}
        />
        {isPassword ? (
          <button
            type="button"
            onClick={() => setShowPassword((prev) => !prev)}
            aria-label={showPassword ? "Hide password" : "Show password"}
            aria-pressed={showPassword}
            className="absolute top-1/2 right-2 inline-flex size-6 -translate-y-1/2 items-center justify-center rounded text-muted-foreground transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
          </button>
        ) : null}
        {/* Focus indicator */}
        {focused && !showError && (
          <div
            className="pointer-events-none absolute inset-0 rounded-lg ring-2 ring-ring/20"
            aria-hidden="true"
          />
        )}
      </div>
      {showError ? (
        <div
          id={`${id}-error`}
          className="animate-fade-in flex items-center gap-1.5 text-xs text-destructive"
          role="alert"
        >
          <AlertCircle className="size-3.5 shrink-0" aria-hidden="true" />
          <span>{errorMessage}</span>
        </div>
      ) : null}
      {labelStrength && !showError ? (
        <div className="animate-fade-in-up space-y-1.5">
          <div className="flex items-center gap-2">
            <p
              id={`${id}-strength`}
              className={cn("text-xs font-medium", strengthColor(labelStrength))}
              aria-live="polite"
            >
              {labelStrength}
            </p>
            <StrengthIndicator variant={strengthVariant(labelStrength)} />
          </div>
        </div>
      ) : null}
      {hint && !showError && !labelStrength ? (
        <p id={`${id}-hint`} className="animate-fade-in text-xs text-muted-foreground">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

function StrengthIndicator({
  variant,
}: {
  variant: "default" | "destructive" | "warning" | "success";
}) {
  const segments = [
    { threshold: 1, color: variant === "destructive" ? "bg-destructive" : "bg-border" },
    {
      threshold: 2,
      color:
        variant === "warning"
          ? "bg-warning"
          : variant === "destructive"
            ? "bg-destructive"
            : "bg-border",
    },
    {
      threshold: 3,
      color:
        variant === "default" ? "bg-primary" : variant === "warning" ? "bg-warning" : "bg-border",
    },
    { threshold: 4, color: variant === "success" ? "bg-success" : "bg-border" },
  ];

  return (
    <div
      className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted"
      role="progressbar"
      aria-valuenow={segments.filter((s) => s.color !== "bg-border").length}
      aria-valuemin={0}
      aria-valuemax={4}
      aria-label="Password strength"
    >
      <div className="flex h-full gap-0.5">
        {segments.map((segment, index) => (
          <div
            key={index}
            className={cn(
              "flex-1 rounded-full transition-all duration-300 ease-out",
              segment.color,
            )}
          />
        ))}
      </div>
    </div>
  );
}

/**
 * A label attached to a control somebody else supplied.
 */
export function WrappedField({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: ReactNode;
  children: ReactElement<{ id?: string; "aria-describedby"?: string }>;
}) {
  const generated = useId();
  const id = children.props.id ?? generated;
  const hintId = hint ? `${id}-hint` : undefined;
  const describedBy =
    [children.props["aria-describedby"], hintId].filter(Boolean).join(" ") || undefined;

  return (
    <div className="space-y-1.5">
      <Label htmlFor={id} className="text-sm font-medium">
        {label}
      </Label>
      {cloneElement(children, { id, "aria-describedby": describedBy })}
      {hint ? (
        <p id={hintId} className="text-xs leading-relaxed text-muted-foreground">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

/** A semantic label and optional hint for a related set of controls. */
export function FieldGroup({
  label,
  hint,
  children,
  className,
}: {
  label: ReactNode;
  hint?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  const generated = useId();
  const hintId = hint ? `${generated}-hint` : undefined;

  return (
    <fieldset className={cn("min-w-0 space-y-1.5", className)} aria-describedby={hintId}>
      <legend className="text-sm font-medium">{label}</legend>
      {children}
      {hint ? (
        <p id={hintId} className="text-xs leading-relaxed text-muted-foreground">
          {hint}
        </p>
      ) : null}
    </fieldset>
  );
}

/**
 * Whatever the last submission had to say.
 */
export function FormFeedback({ state }: { state: FormState }) {
  if (!state.error && !state.message) return null;

  return (
    <Alert
      variant={state.error ? "destructive" : "default"}
      role={state.error ? "alert" : "status"}
      className="animate-fade-in-up"
    >
      {state.error ? <CircleAlert /> : <CircleCheck className="text-success" />}
      <AlertDescription>{state.error ?? state.message}</AlertDescription>
    </Alert>
  );
}

/** A submit button that says what it is doing and cannot be double-pressed. */
export function SubmitButton({
  pending,
  children,
  pendingLabel,
  ...props
}: ComponentProps<typeof Button> & { pending: boolean; pendingLabel?: string }) {
  return (
    <Button
      type="submit"
      disabled={pending}
      {...props}
      className={cn("relative overflow-hidden", props.className)}
    >
      {pending ? (
        <>
          <Loader2 className="size-4 animate-spin" aria-hidden="true" />
          <span className="sr-only">Loading...</span>
        </>
      ) : (
        children
      )}
      {pending ? (pendingLabel ?? "Working…") : null}
    </Button>
  );
}
