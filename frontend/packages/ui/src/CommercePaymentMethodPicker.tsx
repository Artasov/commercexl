"use client";

import type {ReactNode} from "react";

export type CommercePaymentMethodOption = {
  readonly id: string;
  readonly label: string;
  readonly description?: ReactNode;
  readonly badge?: ReactNode;
  readonly disabled?: boolean;
};

export function CommercePaymentMethodPicker({
  options,
  value,
  onValueChange,
  label,
  className,
}: {
  readonly options: readonly CommercePaymentMethodOption[];
  readonly value: string | null;
  readonly onValueChange: (value: string) => void;
  readonly label: string;
  readonly className?: string;
}) {
  return (
    <fieldset className={["oc-payment-methods", className].filter(Boolean).join(" ")}>
      <legend>{label}</legend>
      <div className="oc-payment-methods-grid">
        {options.map((option) => {
          const selected = option.id === value;
          return (
            <button
              key={option.id}
              type="button"
              className="oc-payment-method"
              data-selected={selected ? "true" : undefined}
              aria-pressed={selected}
              disabled={option.disabled}
              onClick={() => onValueChange(option.id)}
            >
              <span className="oc-payment-method-copy">
                <strong>{option.label}</strong>
                {option.description ? <span>{option.description}</span> : null}
              </span>
              {option.badge ? <span className="oc-payment-method-badge">{option.badge}</span> : null}
              <span className="oc-payment-method-radio" aria-hidden />
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}
