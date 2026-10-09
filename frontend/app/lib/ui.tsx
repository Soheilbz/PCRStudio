import { Dialog } from '@base-ui/react/dialog';
import {
  cloneElement,
  useId,
  type FormEvent,
  type ReactElement,
  type ReactNode,
} from 'react';
import { AlertCircle, X } from 'lucide-react';
import { errorMessage } from './api';
export function ErrorNotice({ error }: { error: unknown }) {
  return error ? (
    <div className="notice error" role="alert">
      <AlertCircle size={18} aria-hidden="true" />
      <span>{errorMessage(error)}</span>
    </div>
  ) : null;
}
export function Notice({ children }: { children: ReactNode }) {
  return (
    <div className="notice" role="status">
      {children}
    </div>
  );
}
export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  const id = useId();
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {cloneElement(
        children as ReactElement<{ id: string; 'aria-describedby'?: string }>,
        { id, 'aria-describedby': hint ? `${id}-hint` : undefined },
      )}
      {hint && <small id={`${id}-hint`}>{hint}</small>}
    </div>
  );
}
export function PendingButton({
  pending,
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { pending?: boolean }) {
  return (
    <button
      {...props}
      disabled={pending || props.disabled}
      aria-busy={pending || undefined}
    >
      {pending ? 'Working…' : children}
    </button>
  );
}
export function Modal({
  title,
  description,
  trigger,
  children,
  open,
  onOpenChange,
}: {
  title: string;
  description: string;
  trigger?: ReactNode;
  children: ReactNode;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      {trigger && (
        <Dialog.Trigger className="button primary">{trigger}</Dialog.Trigger>
      )}
      <Dialog.Portal>
        <Dialog.Backdrop className="backdrop" />
        <Dialog.Popup className="modal">
          <div className="row between">
            <Dialog.Title>{title}</Dialog.Title>
            <Dialog.Close className="icon-button" aria-label="Close dialog">
              <X size={20} />
            </Dialog.Close>
          </div>
          <Dialog.Description>{description}</Dialog.Description>
          {children}
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
export function submitted(event: FormEvent) {
  event.preventDefault();
}
export function PageHeading({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle: string;
  action?: ReactNode;
}) {
  return (
    <header className="page-heading">
      <div>
        <h1>{title}</h1>
        <p>{subtitle}</p>
      </div>
      {action}
    </header>
  );
}
export function Loading({ text = 'Loading…' }: { text?: string }) {
  return (
    <div className="card state" role="status">
      {text}
    </div>
  );
}
export function Empty({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="card state">
      <h2>{title}</h2>
      <p>{children}</p>
    </div>
  );
}
