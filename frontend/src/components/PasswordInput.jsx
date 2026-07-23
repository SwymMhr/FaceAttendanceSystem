import { useState } from "react";

// Chromium browsers (Chrome, Brave, Edge) show the saved-credentials
// dropdown on ANY <input type="password">, regardless of autoComplete or
// readOnly — that's an intentional, non-overridable browser policy, not
// something a site can configure away. The one thing that actually works:
// don't use type="password" at all. This renders a text input with
// -webkit-text-security to visually mask it exactly like a password field
// (dots, no visible characters), which Chromium/WebKit browsers never
// recognize as a credential field in the first place.
export default function PasswordInput({ className, style, value, onChange, placeholder, required, autoFocus }) {
  // Random per-mount name/id so nothing matches a saved-credential's field
  // signature even if the masking CSS isn't supported (e.g. Firefox).
  const [fieldId] = useState(() => `pw-${Math.random().toString(36).slice(2)}`);

  return (
    <input
      className={className}
      style={{ WebkitTextSecurity: "disc", ...style }}
      type="text"
      name={fieldId}
      id={fieldId}
      placeholder={placeholder}
      value={value}
      onChange={onChange}
      required={required}
      autoFocus={autoFocus}
      autoComplete="off"
      spellCheck={false}
      autoCapitalize="off"
      autoCorrect="off"
      data-lpignore="true"
      data-1p-ignore
    />
  );
}