"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function EvidenceInput({
  id,
  label,
  type = "text",
  value,
  onChange,
  placeholder,
}: {
  id: string;
  label: string;
  type?: "text" | "number";
  value: (key: string) => string;
  onChange: (key: string, next: string) => void;
  placeholder?: string;
}) {
  return (
    <div>
      <Label htmlFor={id} className="text-xs">
        {label}
      </Label>
      <Input
        id={id}
        type={type}
        value={value(id)}
        onChange={(event) => onChange(id, event.target.value)}
        placeholder={placeholder}
        className="mt-1"
      />
    </div>
  );
}
