/**
 * Whether a post-authentication destination may be followed.
 *
 * Redirect targets are user-controlled query-string data. Merely checking that
 * a string begins with `/` is not sufficient: URL parsers discard ASCII control
 * whitespace before interpreting a network-path reference, so a value such as
 * `/\n//example.org` can become an off-site URL in the browser. Parse against a
 * fixed internal origin and require that the resulting origin is unchanged.
 */
const INTERNAL_ORIGIN = "https://pcrstudio.invalid";
const UNSAFE_URL_CHARACTERS = new Set(["\\"]);

function hasUnsafeUrlCharacters(value: string): boolean {
  for (const character of value) {
    const code = character.charCodeAt(0);
    if (code < 0x20 || code === 0x7f || UNSAFE_URL_CHARACTERS.has(character)) return true;
  }
  return false;
}

export function isSafeDestination(raw: string): boolean {
  if (!raw.startsWith("/") || raw.startsWith("//") || hasUnsafeUrlCharacters(raw)) {
    return false;
  }

  try {
    return new URL(raw, INTERNAL_ORIGIN).origin === INTERNAL_ORIGIN;
  } catch {
    return false;
  }
}
