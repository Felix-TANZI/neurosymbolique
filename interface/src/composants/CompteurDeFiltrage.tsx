/**
 * Restitution du travail de filtrage effectue par le raisonnement.
 *
 * L'ecart entre options examinees et options admissibles constitue la trace
 * visible du raisonnement: il est presente au premier plan plutot que dans un
 * detail, car il distingue une recommandation etablie d'une simple suggestion.
 */

interface ProprietesCompteur {
  examinees: number;
  admissibles: number;
  libelleExaminees?: string;
  libelleAdmissibles?: string;
}

export function CompteurDeFiltrage({
  examinees,
  admissibles,
  libelleExaminees = "examinees",
  libelleAdmissibles = "admissibles",
}: ProprietesCompteur) {
  const ecartees = Math.max(examinees - admissibles, 0);
  const proportion = examinees > 0 ? (admissibles / examinees) * 100 : 0;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-baseline gap-6">
        <div>
          <p className="font-display text-[var(--text-enorme)] leading-none text-accent">
            {admissibles}
          </p>
          <p className="mt-1 text-sm text-service">{libelleAdmissibles}</p>
        </div>
        <div className="pb-2">
          <p className="font-display text-3xl leading-none text-encre">
            {examinees}
          </p>
          <p className="mt-1 text-sm text-service">{libelleExaminees}</p>
        </div>
      </div>

      <div>
        <div
          className="h-1.5 w-full overflow-hidden rounded-[var(--radius-pastille)] bg-sourd"
          role="img"
          aria-label={`${admissibles} options admissibles sur ${examinees} examinees`}
        >
          <div
            className="h-full rounded-[var(--radius-pastille)] bg-accent transition-[width] duration-500"
            style={{ width: `${proportion}%` }}
          />
        </div>
        <p className="mt-2 text-sm text-service">
          {ecartees} ecartees, chacune avec son motif
        </p>
      </div>
    </div>
  );
}