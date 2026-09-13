/**
 * Marque de l'application.
 *
 * Deux sources convergent vers une decision: la lecture de l'enonce et les
 * regles de l'etablissement, que le systeme compose avant de proposer. Le
 * trace reprend celui de l'icone d'onglet, de sorte que l'une et l'autre se
 * reconnaissent.
 */

export function Logo({ taille = 32 }: { taille?: number }) {
  return (
    <svg
      width={taille}
      height={taille}
      viewBox="0 0 64 64"
      role="img"
      aria-label="Neuro"
      className="shrink-0"
    >
      <rect width="64" height="64" rx="15" fill="var(--color-encre)" />
      <path
        d="M19 21 43 32M19 43l24-11"
        stroke="var(--color-creme)"
        strokeWidth="4.5"
        strokeLinecap="round"
      />
      <circle cx="19" cy="21" r="6" fill="var(--color-creme)" />
      <circle cx="19" cy="43" r="6" fill="var(--color-creme)" />
      <circle cx="44" cy="32" r="9.5" fill="var(--color-accent)" />
      <circle cx="44" cy="32" r="3.2" fill="var(--color-creme)" />
    </svg>
  );
}
