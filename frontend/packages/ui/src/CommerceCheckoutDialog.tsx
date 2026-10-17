"use client";

import {Button, Dialog} from "@orcestr/ui";
import type {ReactNode} from "react";

export function CommerceCheckoutDialog({
  open,
  onOpenChange,
  title,
  description,
  children,
  closeLabel,
  closeDisabled = false,
  maxWidth = 720,
  className,
}: {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly title: ReactNode;
  readonly description?: ReactNode;
  readonly children: ReactNode;
  readonly closeLabel: ReactNode;
  readonly closeDisabled?: boolean;
  readonly maxWidth?: number;
  readonly className?: string;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={(nextOpen) => {
      if (!nextOpen && closeDisabled) return;
      onOpenChange(nextOpen);
    }}>
      <Dialog.Content
        maxWidth={maxWidth}
        closeOnOverlayClick={!closeDisabled}
        className={["oc-checkout-dialog", className].filter(Boolean).join(" ")}
      >
        <div className="oc-checkout-dialog-header">
          <Dialog.Title>{title}</Dialog.Title>
          <Button className="oc-checkout-dialog-close" v="ghost" size={1} type="button"
            disabled={closeDisabled} onClick={() => {if (!closeDisabled) onOpenChange(false);}}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18" /></svg>
            <span className="oc-visually-hidden">{closeLabel}</span>
          </Button>
        </div>
        {description ? <Dialog.Description>{description}</Dialog.Description> : null}
        <div className="oc-checkout-dialog-body">{children}</div>
      </Dialog.Content>
    </Dialog.Root>
  );
}
