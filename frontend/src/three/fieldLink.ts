// Wording of the system page's link to its field's images. Kept apart from SystemPage so it can be
// tested without rendering the page.
//
// A system's field is the challenge target's cutout, which is not always where the system's
// primary is: the Epsilon Indi system page shows eps Ind A's coordinates, but its field is centred
// on eps Ind B (~402" away, outside the 0.15° cutout). So the link names the field (the manifest's
// field name) instead of "it".

/** What the system page knows about a field from the manifest. */
export interface FieldLinkInfo {
  name: string;
  synthetic: boolean;
}

/** Link text for a system's field; `syntheticSystem` covers a synthetic system whose field is not in the map. */
export function fieldLinkLabel(field: FieldLinkInfo | undefined, syntheticSystem = false): string {
  // Never call a synthetic field (or the field of a synthetic system) "SPHEREx images".
  if (syntheticSystem || field?.synthetic) return 'See the synthetic demo field (not SPHEREx) →';
  const name = field?.name.trim();
  return name ? `See ${name} in SPHEREx images →` : 'See it in SPHEREx images →';
}
