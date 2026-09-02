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
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Content
        maxWidth={maxWidth}
        closeOnOverlayClick={!closeDisabled}
        className={["oc-checkout-dialog", className].filter(Boolean).join(" ")}
      >
        <Dialog.Title>{title}</Dialog.Title>
        {description ? <Dialog.Description>{description}</Dialog.Description> : null}
        <div className="oc-checkout-dialog-body">{children}</div>
        <Dialog.Close>
          <Button fullWidth v="ghost" type="button" disabled={closeDisabled}>
            {closeLabel}
          </Button>
        </Dialog.Close>
      </Dialog.Content>
    </Dialog.Root>
  );
}
