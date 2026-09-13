/**
 * Memoire de la presentation du guide.
 *
 * Le guide s'ouvre de lui-meme a la premiere visite, puis a chaque nouveau
 * deploiement: l'empreinte de construction change alors, et ce que l'on
 * savait de l'application peut ne plus etre exact. Entre deux deploiements,
 * il demeure accessible a la demande sans s'imposer.
 *
 * La memoire est propre au navigateur. Son absence, en navigation privee ou
 * lorsque le stockage est refuse, fait simplement reapparaitre le guide.
 */

const CLE = "neuro.guide.vu";

const EMPREINTE: string =
  typeof import.meta.env.VITE_CONSTRUCTION === "string"
    ? import.meta.env.VITE_CONSTRUCTION
    : "developpement";

export function guideAPresenter(): boolean {
  try {
    return window.localStorage.getItem(CLE) !== EMPREINTE;
  } catch {
    return true;
  }
}

export function marquerGuideVu(): void {
  try {
    window.localStorage.setItem(CLE, EMPREINTE);
  } catch {
    // Le stockage est indisponible: le guide reapparaitra, sans autre effet.
  }
}
